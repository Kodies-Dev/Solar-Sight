# SolarSight frontend

React 19 + Vite dashboard: a Mapbox map of Silesian cities and, for the selected
city, the 24-hour PV production forecast served by the Flask API. UI text is in Polish.

## Run

```bash
cp .env.example .env    # fill in VITE_MAPBOX_ACCESS_TOKEN
npm install
npm run dev
```

| Variable | Purpose | Default |
|---|---|---|
| `VITE_MAPBOX_ACCESS_TOKEN` | Mapbox GL access token | required |
| `VITE_API_URL` | Base URL of the Flask API | `http://localhost:5001` |

## Structure

- `src/App.jsx` – fetches `/analyze` for the selected city
- `src/components/Map/` – Mapbox map with city markers (`src/data/cities.json`)
- `src/components/PredictionModal*/` – side panel: stats, hourly chart, weather strip
- `src/components/WeatherIcon/` – WMO weather code → icon
