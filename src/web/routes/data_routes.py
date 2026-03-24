from flask import Blueprint, request, jsonify
import sqlite3
import os
from datetime import datetime
from services.data_services import open_db

data_bp = Blueprint('data', __name__)

@data_bp.route('/upload/raw', methods=['POST'])
def upload_raw():
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400

    try:
        # Field mapping
        temp = data.get("temp_c", data.get("temp", 0))
        hum  = data.get("humidity", data.get("hum", 0))
        gas  = data.get("gas_pct", data.get("gas", 0))
        lux  = data.get("lux", 0)
        pres = data.get("pressure", data.get("press", 0))
        device_id = int(data.get("device_id", data.get("id", 0)))

        # Handle Timestamp: Expecting a Unix epoch (float/int)
        raw_ts = data.get("timestamp")
        if raw_ts:
            dt_object = datetime.fromtimestamp(float(raw_ts))
        else:
            dt_object = datetime.now()
            
        formatted_time = dt_object.strftime("%Y-%m-%d %H:%M:%S")

        with open_db() as conn:
            conn.execute("""
                INSERT INTO live_data (date_time, temp, hum, lux, gas_pct, press, device_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (formatted_time, temp, hum, lux, gas, pres, device_id))
            conn.commit()

        return jsonify({"status": "stored", "at": formatted_time}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500