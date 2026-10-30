"""Flask API serving SolarSight forecasts.

Run from the repository root (after `pip install -e .`):
    python backend/app.py
"""
from __future__ import annotations

import logging
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

from solarsight import __version__
from solarsight.config import DEFAULT_CITY
from solarsight.inference import load_model, predict, simulate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = Flask(__name__)
CORS(app)

# Load the model at startup so the first request does not pay for joblib.load()
try:
    load_model()
    app.logger.info("Model loaded successfully")
except Exception as exc:  # noqa: BLE001 - the API still starts and reports errors per request
    app.logger.error("Failed to load model at startup: %s", exc)


def _now() -> str:
    return datetime.now().isoformat()


def _error(message: str, status: int):
    return jsonify({"status": "error", "message": message, "timestamp": _now()}), status


def _read_city(payload: dict) -> str | None:
    city = request.args.get("city") or payload.get("city") or DEFAULT_CITY.lower()
    if not isinstance(city, str) or not city.strip():
        return None
    return city.strip()


def _records(results) -> list[dict]:
    results["timestamp"] = results["timestamp"].astype(str)
    return results.to_dict(orient="records")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "App working", "timestamp": _now(), "version": __version__}), 200


@app.route("/analyze", methods=["POST"])
def analyze():
    payload = request.get_json(silent=True) or {}
    city = _read_city(payload)
    if city is None:
        return _error("Parameter 'city' must be a non-empty string", 400)

    try:
        data = _records(predict(city=city))
    except ValueError as exc:
        app.logger.warning("Invalid city '%s': %s", city, exc)
        return _error(str(exc), 400)
    except RuntimeError as exc:
        app.logger.warning("Upstream error (Open-Meteo): %s", exc)
        return _error(str(exc), 502)
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Error during prediction")
        return _error(str(exc), 500)

    return jsonify({"status": "success", "message": "Analyze done", "city": city,
                    "data": data, "count": len(data), "timestamp": _now()}), 200


@app.route("/simulate", methods=["POST"])
def simulate_cloud_cover():
    payload = request.get_json(silent=True) or {}
    city = _read_city(payload)
    if city is None:
        return _error("Parameter 'city' must be a non-empty string", 400)

    try:
        cloud_cover = float(payload.get("cloud_cover", request.args.get("cloud_cover", 0)))
    except (TypeError, ValueError):
        return _error("Parameter 'cloud_cover' must be a number", 400)
    if not 0.0 <= cloud_cover <= 100.0:
        return _error("Parameter 'cloud_cover' must be in range [0, 100]", 400)

    try:
        data = _records(simulate(city=city, cloud_cover=cloud_cover))
    except ValueError as exc:
        app.logger.warning("Invalid input for /simulate: %s", exc)
        return _error(str(exc), 400)
    except RuntimeError as exc:
        app.logger.warning("Upstream error (Open-Meteo): %s", exc)
        return _error(str(exc), 502)
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Error during simulation")
        return _error(str(exc), 500)

    return jsonify({"status": "success", "message": "Simulation done", "city": city,
                    "cloud_cover": cloud_cover, "data": data, "count": len(data),
                    "timestamp": _now()}), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
