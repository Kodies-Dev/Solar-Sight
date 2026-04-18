from flask import Flask, jsonify, request
import json
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Dodaj parent directory do sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trained_model_usage.predicting_mwh import predykuj

app = Flask(__name__)


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "ok",
        "message": "Aplikacja działa prawidłowo",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0"
    }), 200


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # Pobierz wyniki predykcji z modelu
        wyniki = predykuj()
        
        # Konwertuj DataFrame na format JSON
        wyniki['timestamp'] = wyniki['timestamp'].astype(str)
        wyniki_json = wyniki.to_dict(orient='records')
        
        return jsonify({
            "status": "success",
            "message": "Analiza ukończona",
            "data": wyniki_json,
            "count": len(wyniki_json),
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
