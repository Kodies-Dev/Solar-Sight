from flask import Flask, jsonify, request
import json
import logging
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trained_model_usage.predicting_mwh import predykuj, _get_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = Flask(__name__)

# Pre-load model at startup — first request doesn't pay the joblib.load() cost
try:
    _get_model()
    app.logger.info("Model loaded successfully")
except Exception as exc:
    app.logger.error("Failed to load model at startup: %s", exc)


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "ok",
        "message": "App working",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0"
    }), 200


@app.route('/analyze', methods=['POST'])
def analyze():
    payload = request.get_json(silent=True) or {}
    city = request.args.get('city') or payload.get('city') or 'gliwice'

    if not isinstance(city, str) or not city.strip():
        return jsonify({
            "status": "error",
            "message": "Parameter 'city' must be a non-empty string",
            "timestamp": datetime.now().isoformat()
        }), 400

    city = city.strip()

    try:
        results = predykuj(city=city)
        results['timestamp'] = results['timestamp'].astype(str)
        results_json = results.to_dict(orient='records')

        return jsonify({
            "status": "success",
            "message": "Analyze done",
            "city": city,
            "data": results_json,
            "count": len(results_json),
            "timestamp": datetime.now().isoformat()
        }), 200

    except ValueError as e:
        app.logger.warning("Invalid city '%s': %s", city, e)
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 400

    except RuntimeError as e:
        app.logger.warning("Upstream error (Open-Meteo): %s", e)
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 502

    except Exception as e:
        app.logger.exception("Error during prediction")
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
