import os
import sqlite3
from flask import Blueprint, render_template, jsonify, request
from services.data_services import open_db

# Define the blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/')
def index():
    return render_template('index.html')

@api_bp.route('/api/sondes')
def api_sondes():
    conn = open_db()
    if not conn: return jsonify([])
    rows = conn.execute('SELECT DISTINCT sonde_id FROM mesures ORDER BY sonde_id ASC').fetchall()
    conn.close()
    return jsonify([row['sonde_id'] for row in rows])

@api_bp.route('/api/data')
def api_data():
    sonde_id = request.args.get('sonde', 1, type=int)
    conn = open_db()
    if not conn: return jsonify({"error": "DB Link Down"}), 500
    row = conn.execute('SELECT * FROM mesures WHERE sonde_id = ? ORDER BY date_time DESC LIMIT 1', (sonde_id,)).fetchone()
    conn.close()
    return jsonify(dict(row)) if row else (jsonify({"error": "Empty"}), 404)

@api_bp.route('/api/history')
def api_history():
    mode = request.args.get('mode', 'day')
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    sonde_id = request.args.get('sonde', 1, type=int)
    
    conn = open_db()
    if not conn: return jsonify({"error": "DB Error"}), 500

    mapping = """time_label AS date_time, temp_avg AS temp, hum_avg AS hum, lux_avg AS lux, gas_avg AS gas_pct, press_avg AS press, air_avg AS air_pct"""

    try:
        args = (sonde_id, start_date, end_date)
        if mode == 'year':
            query = f"SELECT {mapping} FROM daily_history WHERE sonde_id=? AND date(time_label) BETWEEN date(?) AND date(?) ORDER BY time_label ASC"
        elif mode in ['month', 'week']:
            query = f"SELECT {mapping} FROM hourly_history WHERE sonde_id=? AND time_label BETWEEN ? AND ? ORDER BY time_label ASC"
        else:
            check_raw = conn.execute("SELECT 1 FROM mesures WHERE sonde_id=? AND date_time BETWEEN ? AND ? LIMIT 1", args).fetchone()
            if check_raw:
                query = "SELECT * FROM mesures WHERE sonde_id=? AND date_time BETWEEN ? AND ? ORDER BY date_time ASC"
            else:
                check_hour = conn.execute("SELECT 1 FROM hourly_history WHERE sonde_id=? AND time_label BETWEEN ? AND ? LIMIT 1", args).fetchone()
                if check_hour:
                    query = f"SELECT {mapping} FROM hourly_history WHERE sonde_id=? AND time_label BETWEEN ? AND ? ORDER BY time_label ASC"
                else:
                    query = f"SELECT {mapping} FROM daily_history WHERE sonde_id=? AND date(time_label) BETWEEN date(?) AND date(?) ORDER BY time_label ASC"

        rows = conn.execute(query, args).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/limits')
def api_limits():
    sonde_id = request.args.get('sonde', 1, type=int)
    conn = open_db()
    if not conn: return jsonify({"error": "DB Link Down"}), 500
    row = conn.execute('SELECT MIN(time_label) as first_date FROM daily_history WHERE sonde_id=?', (sonde_id,)).fetchone()
    conn.close()
    return jsonify(dict(row))