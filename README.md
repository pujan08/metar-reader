# ✈ METAR Reader — Airport Weather Decoder

A clean, lightweight Flask web app that fetches live **METAR** reports for any airport and translates the raw coded string into plain English — no aviation knowledge required.

---

## What is METAR?

**METAR** (Meteorological Aerodrome Report) is the standard format used worldwide to report current weather conditions at airports. A typical raw METAR looks like this:

```
KLAX 031853Z 25012KT 10SM FEW025 SCT250 18/08 A2994
```

This app decodes that into human-readable output:
- **Wind:** From the West at 14 mph
- **Visibility:** 10+ miles
- **Sky:** A few clouds at 2,500 ft; Scattered clouds at 25,000 ft
- **Temperature:** 64°F (18°C)
- **Dewpoint:** 46°F (8°C)
- **Pressure:** 29.94 inHg

---

## Features

- **Live data** — fetches real-time METARs from the [Aviation Weather Center API](https://aviationweather.gov/api/data/metar)
- **Full decoder** — parses wind, visibility, sky conditions, present weather, temperature, dewpoint, and altimeter
- **Plain-English summaries** — converts coded weather phenomena (e.g. `-TSRA`, `BKN040CB`) into readable descriptions
- **Both unit systems** — temperatures shown in °F and °C; winds in mph (converted from knots)
- **Compass directions** — wind direction converted from degrees to cardinal/intercardinal labels (e.g. 270° → "From the West")
- **Raw METAR toggle** — collapsible section shows the original raw string for reference
- **Quick-search examples** — one-click buttons for popular airports (KHIO, KLAX, KJFK, KORD, KSEA)
- **Responsive UI** — works on desktop and mobile

---

## Tech Stack

| Layer     | Technology                        |
|-----------|-----------------------------------|
| Backend   | Python 3 · Flask                  |
| Frontend  | Vanilla HTML/CSS/JavaScript       |
| Data      | Aviation Weather Center REST API  |
| Packaging | pip · `requirements.txt`          |

---

## Getting Started

### Prerequisites

- Python 3.9+
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/pujan08/metar-reader.git
cd metar-reader

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Open your browser and go to **http://127.0.0.1:5000**

---

## Usage

1. Type a **4-letter ICAO airport code** (e.g. `KLAX`, `KJFK`, `EGLL`) into the search box
2. Press **Get Weather** or hit **Enter**
3. View the decoded weather report with a plain-English summary and detailed breakdown
4. Expand the **Raw METAR** section at the bottom to see the original coded string

> **Tip:** US airports use 4-letter ICAO codes starting with **K** (e.g. `KSEA` for Seattle-Tacoma). International airports use their own regional prefixes (e.g. `EGLL` for London Heathrow, `RJTT` for Tokyo Haneda).

---

## Project Structure

```
metar-reader/
├── app.py               # Flask app — METAR parser, decoder, and API routes
├── requirements.txt     # Python dependencies
└── templates/
    └── index.html       # Single-page frontend (HTML + CSS + JS)
```

---

## API Endpoint

The app exposes a simple JSON endpoint you can also call directly:

```
GET /api/weather?airport=KLAX
```

**Example response:**
```json
{
  "airport": "KLAX",
  "raw": "KLAX 031853Z 25012KT 10SM FEW025 SCT250 18/08 A2994",
  "summary": "A few clouds at 2,500 ft. Temperature 64°F (18°C). Winds: From the West at 14 mph. Visibility 10+ miles.",
  "decoded": {
    "station": "KLAX",
    "time": "18:53 UTC",
    "wind": "From the West at 14 mph",
    "visibility": "10+ miles",
    "sky": "A few clouds at 2,500 ft; Scattered clouds at 25,000 ft",
    "temperature": "64°F (18°C)",
    "dewpoint": "46°F (8°C)",
    "altimeter": "29.94 inHg",
    "weather": null
  }
}
```

---

## License

This project is open source and available under the [MIT License](LICENSE).

---

## Acknowledgements

- Weather data provided by the **[NOAA Aviation Weather Center](https://aviationweather.gov/)**
- METAR format documentation: **[FAA Aviation Weather Services (AC 00-45)](https://www.faa.gov/)**
