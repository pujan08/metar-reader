import re
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Unit / direction helpers
# ---------------------------------------------------------------------------

def degrees_to_compass(degrees):
    directions = [
        'North', 'North-Northeast', 'Northeast', 'East-Northeast',
        'East', 'East-Southeast', 'Southeast', 'South-Southeast',
        'South', 'South-Southwest', 'Southwest', 'West-Southwest',
        'West', 'West-Northwest', 'Northwest', 'North-Northwest',
    ]
    return directions[round(degrees / 22.5) % 16]


def celsius_to_fahrenheit(c):
    return round((c * 9 / 5) + 32)


def knots_to_mph(knots):
    return round(knots * 1.15078)


def parse_temp(s):
    """Parse METAR temperature string like '12' or 'M03' (minus 3)."""
    if s.startswith('M'):
        return -int(s[1:])
    return int(s)


# ---------------------------------------------------------------------------
# Weather-phenomenon decoder
# ---------------------------------------------------------------------------

DESCRIPTORS = {
    'MI': 'shallow', 'BC': 'patchy', 'PR': 'partial',
    'DR': 'low drifting', 'BL': 'blowing', 'SH': 'shower',
    'TS': 'thunderstorm', 'FZ': 'freezing',
}
PRECIPITATION = {
    'DZ': 'drizzle', 'RA': 'rain', 'SN': 'snow', 'SG': 'snow grains',
    'IC': 'ice crystals', 'PL': 'ice pellets', 'GR': 'hail',
    'GS': 'small hail', 'UP': 'unknown precipitation',
}
OBSCURATION = {
    'BR': 'mist', 'FG': 'fog', 'FU': 'smoke', 'VA': 'volcanic ash',
    'DU': 'dust', 'SA': 'sand', 'HZ': 'haze', 'PY': 'spray',
}
OTHER_WX = {
    'PO': 'dust/sand whirls', 'SQ': 'squalls', 'FC': 'funnel cloud',
    'SS': 'sandstorm', 'DS': 'dust storm',
}


def decode_wx_code(wx):
    """Convert a single weather code (e.g. '-TSRA') to plain English."""
    tokens = []
    rem = wx

    # Intensity / proximity prefix
    if rem.startswith('+'):
        tokens.append('heavy')
        rem = rem[1:]
    elif rem.startswith('-'):
        tokens.append('light')
        rem = rem[1:]
    elif rem.startswith('VC'):
        tokens.append('nearby')
        rem = rem[2:]

    # Up to two descriptors
    for _ in range(2):
        matched = False
        for code, label in DESCRIPTORS.items():
            if rem.startswith(code):
                tokens.append(label)
                rem = rem[len(code):]
                matched = True
                break
        if not matched:
            break

    # One or more phenomenon codes
    while rem:
        matched = False
        for mapping in (PRECIPITATION, OBSCURATION, OTHER_WX):
            for code, label in mapping.items():
                if rem.startswith(code):
                    tokens.append(label)
                    rem = rem[len(code):]
                    matched = True
                    break
            if matched:
                break
        if not matched:
            if rem:
                tokens.append(rem)
            break

    return ' '.join(tokens)


WX_PATTERN = re.compile(
    r'^(\+|-|VC)?(MI|BC|PR|DR|BL|SH|TS|FZ){0,2}'
    r'(DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS|TS)+$'
)


# ---------------------------------------------------------------------------
# Sky-condition decoder
# ---------------------------------------------------------------------------

COVER_LABELS = {
    'CLEAR': 'Clear skies',
    'FEW': 'A few clouds',
    'SCT': 'Scattered clouds',
    'BKN': 'Mostly cloudy',
    'OVC': 'Overcast',
    'VV': 'Sky obscured',
}

SKY_PATTERN = re.compile(
    r'^(SKC|CLR|NSC|NCD|CAVOK|FEW|SCT|BKN|OVC|VV)\d{0,3}(CB|TCU)?$'
)


def decode_sky(sky_list):
    if not sky_list:
        return None
    if sky_list[0][0] == 'CLEAR':
        return 'Clear skies'
    parts = []
    for cover, height, ctype in sky_list:
        desc = COVER_LABELS.get(cover, cover)
        if height:
            desc += f' at {height:,} ft'
        if ctype == 'CB':
            desc += ' (cumulonimbus / thunderstorm clouds)'
        elif ctype == 'TCU':
            desc += ' (towering cumulus clouds)'
        parts.append(desc)
    return '; '.join(parts)


# ---------------------------------------------------------------------------
# Main METAR parser
# ---------------------------------------------------------------------------

def decode_metar(raw):
    """Parse a raw METAR string and return a dict of decoded fields."""
    body = raw.strip().split(' RMK')[0]
    parts = body.split()
    n = len(parts)
    idx = 0

    result = {
        'raw': raw.strip(),
        'station': None, 'time': None,
        'wind': None, 'visibility': None,
        'weather': None, 'sky': None,
        'temperature': None, 'dewpoint': None,
        'altimeter': None,
    }

    # Optional type keyword
    if idx < n and parts[idx] in ('METAR', 'SPECI'):
        idx += 1

    # Station ID
    if idx < n:
        result['station'] = parts[idx]
        idx += 1

    # Timestamp  DDHHmmZ
    if idx < n and re.match(r'^\d{6}Z$', parts[idx]):
        dt = parts[idx]
        hour, minute = int(dt[2:4]), int(dt[4:6])
        result['time'] = f'{hour:02d}:{minute:02d} UTC'
        idx += 1

    # AUTO / COR / NIL
    if idx < n and parts[idx] in ('AUTO', 'COR'):
        idx += 1
    if idx < n and parts[idx] == 'NIL':
        result['error'] = 'No observation available (NIL report).'
        return result

    # Wind
    if idx < n:
        m = re.match(r'^(VRB|\d{3})(\d{2,3})(G(\d{2,3}))?KT$', parts[idx])
        if m:
            direction, speed_kt = m.group(1), int(m.group(2))
            gust_kt = m.group(4)
            speed_mph = knots_to_mph(speed_kt)
            if speed_kt == 0:
                result['wind'] = 'Calm'
            elif direction == 'VRB':
                result['wind'] = f'Variable at {speed_mph} mph'
            else:
                compass = degrees_to_compass(int(direction))
                result['wind'] = f'From the {compass} at {speed_mph} mph'
            if gust_kt:
                result['wind'] += f', gusting to {knots_to_mph(int(gust_kt))} mph'
            idx += 1

    # Wind variable direction (e.g. 280V350) — informational, skip
    if idx < n and re.match(r'^\d{3}V\d{3}$', parts[idx]):
        idx += 1

    # Visibility
    if idx < n:
        p = parts[idx]
        if re.match(r'^M?\d+SM$', p):
            if p.startswith('M'):
                result['visibility'] = f'Less than {p[1:-2]} mile'
            else:
                v = int(p[:-2])
                result['visibility'] = f'{v}+ miles' if v >= 10 else f'{v} mile{"s" if v != 1 else ""}'
            idx += 1
        elif re.match(r'^M?\d+/\d+SM$', p):
            fm = re.match(r'^M?(\d+)/(\d+)SM$', p)
            result['visibility'] = f'{int(fm.group(1))/int(fm.group(2)):.2f} miles'
            idx += 1
        elif re.match(r'^\d+$', p) and idx + 1 < n and re.match(r'^\d+/\d+SM$', parts[idx + 1]):
            whole = int(p)
            fm = re.match(r'^(\d+)/(\d+)SM$', parts[idx + 1])
            frac = int(fm.group(1)) / int(fm.group(2))
            result['visibility'] = f'{whole + frac:.1f} miles'
            idx += 2

    # RVR — skip
    while idx < n and re.match(r'^R\d+[LRC]?/[MP]?\d+', parts[idx]):
        idx += 1

    # Present weather
    wx_list = []
    while idx < n and WX_PATTERN.match(parts[idx]):
        wx_list.append(decode_wx_code(parts[idx]))
        idx += 1
    if wx_list:
        result['weather'] = ', '.join(wx_list)

    # Sky conditions
    sky_list = []
    while idx < n and SKY_PATTERN.match(parts[idx]):
        p = parts[idx]
        if p in ('SKC', 'CLR', 'NSC', 'NCD', 'CAVOK'):
            sky_list.append(('CLEAR', 0, None))
        else:
            sm = re.match(r'^(FEW|SCT|BKN|OVC|VV)(\d{3})(CB|TCU)?$', p)
            if sm:
                sky_list.append((sm.group(1), int(sm.group(2)) * 100, sm.group(3)))
        idx += 1
    result['sky'] = decode_sky(sky_list)

    # Temperature / dewpoint
    if idx < n:
        m = re.match(r'^(M?\d+)/(M?\d*)$', parts[idx])
        if m:
            temp_c = parse_temp(m.group(1))
            result['temperature'] = f'{celsius_to_fahrenheit(temp_c)}°F ({temp_c}°C)'
            if m.group(2):
                dew_c = parse_temp(m.group(2))
                result['dewpoint'] = f'{celsius_to_fahrenheit(dew_c)}°F ({dew_c}°C)'
            idx += 1

    # Altimeter
    if idx < n:
        m = re.match(r'^A(\d{4})$', parts[idx])
        if m:
            result['altimeter'] = f'{int(m.group(1)) / 100:.2f} inHg'
            idx += 1
        else:
            m = re.match(r'^Q(\d{4})$', parts[idx])
            if m:
                result['altimeter'] = f'{m.group(1)} hPa'
                idx += 1

    return result


def build_summary(d):
    """Assemble a single friendly sentence from decoded METAR fields."""
    pieces = []
    if d.get('sky'):
        pieces.append(d['sky'])
    if d.get('weather'):
        pieces.append(d['weather'].capitalize())
    if d.get('temperature'):
        pieces.append(f'Temperature {d["temperature"]}')
    if d.get('wind'):
        pieces.append(f'Winds: {d["wind"]}')
    if d.get('visibility'):
        pieces.append(f'Visibility {d["visibility"]}')
    if d.get('dewpoint'):
        pieces.append(f'Dewpoint {d["dewpoint"]}')
    if d.get('altimeter'):
        pieces.append(f'Pressure {d["altimeter"]}')
    return '. '.join(pieces) + '.' if pieces else 'No weather data decoded.'


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/weather')
def get_weather():
    airport = request.args.get('airport', '').strip().upper()

    if not airport:
        return jsonify({'error': 'Please enter an airport code.'}), 400
    if not re.match(r'^[A-Z0-9]{2,5}$', airport):
        return jsonify({'error': 'Invalid airport code. Use 3–5 letters/numbers (e.g. KHIO, KLAX).'}), 400

    try:
        resp = requests.get(
            'https://aviationweather.gov/api/data/metar',
            params={'ids': airport},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.text.strip()

        if not raw:
            return jsonify({'error': f'No METAR found for {airport}. Verify the airport code.'}), 404

        # Use the first line only (some responses contain multiple)
        raw = raw.splitlines()[0].strip()

        decoded = decode_metar(raw)
        if 'error' in decoded:
            return jsonify({'error': decoded['error']}), 404

        return jsonify({
            'airport': airport,
            'raw': raw,
            'decoded': decoded,
            'summary': build_summary(decoded),
        })

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out. Please try again.'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Could not fetch weather data: {e}'}), 502


if __name__ == '__main__':
    app.run(debug=True)
