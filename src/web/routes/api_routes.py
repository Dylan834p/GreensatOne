import os
import sqlite3
from flask import Blueprint, render_template, jsonify, request
from services.data_services import open_db

# Define the blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/')
def index():
    return render_template('index.html')

@api_bp.route('/aggregate')
def aggregate():
    return render_template('aggregate.html')

@api_bp.route('/api/sondes')
def api_sondes():
    conn = open_db()
    if not conn: return jsonify([])
    rows = conn.execute('SELECT DISTINCT device_id FROM live_data ORDER BY device_id ASC').fetchall()
    conn.close()
    return jsonify([row['device_id'] for row in rows])

@api_bp.route('/api/data')
def api_data():
    device_id = request.args.get('sonde', 1, type=int)
    conn = open_db()
    if not conn: return jsonify({"error": "DB Link Down"}), 500
    row = conn.execute('SELECT * FROM live_data WHERE device_id = ? ORDER BY date_time DESC LIMIT 1', (device_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)) if row else (jsonify({"error": "Data not found!"}), 200)

@api_bp.route('/api/history')
def api_history():
    mode = request.args.get('mode', 'day')
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    device_id = request.args.get('sonde', 1, type=int)
    
    conn = open_db()
    if not conn: return jsonify({"error": "DB Error"}), 500

    mapping = "time_label AS date_time, temp_avg AS temp, hum_avg AS hum, lux_avg AS lux, gas_avg AS gas_pct, press_avg AS press"

    try:
        args = (device_id, start_date, end_date)
        
        # Default query for 'day' mode if data is missing everywhere
        query = f"SELECT {mapping} FROM daily_history WHERE device_id=? AND date(time_label) BETWEEN date(?) AND date(?) ORDER BY time_label ASC"

        if mode == 'year':
            query = f"SELECT {mapping} FROM daily_history WHERE device_id=? AND date(time_label) BETWEEN date(?) AND date(?) ORDER BY time_label ASC"
        elif mode in ['month', 'week']:
            query = f"SELECT {mapping} FROM hourly_history WHERE device_id=? AND time_label BETWEEN ? AND ? ORDER BY time_label ASC"
        elif mode == 'day':
            if conn.execute("SELECT 1 FROM live_data WHERE device_id=? AND date_time BETWEEN ? AND ? LIMIT 1", args).fetchone():
                query = "SELECT * FROM live_data WHERE device_id=? AND date_time BETWEEN ? AND ? ORDER BY date_time ASC"
            elif conn.execute("SELECT 1 FROM hourly_history WHERE device_id=? AND time_label BETWEEN ? AND ? LIMIT 1", args).fetchone():
                query = f"SELECT {mapping} FROM hourly_history WHERE device_id=? AND time_label BETWEEN ? AND ? ORDER BY time_label ASC"

        rows = conn.execute(query, args).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]) # Returns [] if empty, preventing 500 error
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/limits')
def api_limits():
    device_id = request.args.get('sonde', 1, type=int)
    conn = open_db()
    if not conn: return jsonify({"error": "DB Link Down"}), 500
    row = conn.execute('SELECT MIN(time_label) as first_date FROM daily_history WHERE device_id=?', (device_id,)).fetchone()
    conn.close()
    return jsonify(dict(row))