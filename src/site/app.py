import os
import sqlite3
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SITE_DIR)
DB_PATH = os.path.join(BASE_DIR, 'backend', 'greensat.db')

def get_db_connection():
    if not os.path.exists(DB_PATH):
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL;')
        return conn
    except Exception:
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def api_data():
    """Real-time data: uses the 'mesures' table."""
    conn = get_db_connection()
    if not conn: return jsonify({"error": "DB Link Down"}), 500
    row = conn.execute('SELECT * FROM mesures ORDER BY date_time DESC LIMIT 1').fetchone()
    conn.close()
    return jsonify(dict(row)) if row else (jsonify({"error": "Empty"}), 404)

@app.route('/api/history')
def api_history():
    mode = request.args.get('mode', 'day')
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    conn = get_db_connection()
    if not conn: return jsonify({"error": "DB Error"}), 500

    mapping = """
        time_label AS date_time, 
        temp_avg AS temp, hum_avg AS hum, lux_avg AS lux, 
        gas_avg AS gas_pct, press_avg AS press, air_avg AS air_pct
    """

    try:
        if mode == 'year':
            query = f"SELECT {mapping} FROM daily_history WHERE date(time_label) BETWEEN date(?) AND date(?) ORDER BY time_label ASC"
        
        elif mode in ['month', 'week']:
            query = f"SELECT {mapping} FROM hourly_history WHERE time_label BETWEEN ? AND ? ORDER BY time_label ASC"
        
        else:
            check_raw = conn.execute("SELECT 1 FROM mesures WHERE date_time BETWEEN ? AND ? LIMIT 1", (start_date, end_date)).fetchone()
            if check_raw:
                query = "SELECT * FROM mesures WHERE date_time BETWEEN ? AND ? ORDER BY date_time ASC"
            else:
                check_hour = conn.execute("SELECT 1 FROM hourly_history WHERE time_label BETWEEN ? AND ? LIMIT 1", (start_date, end_date)).fetchone()
                if check_hour:
                    query = f"SELECT {mapping} FROM hourly_history WHERE time_label BETWEEN ? AND ? ORDER BY time_label ASC"
                else:
                    query = f"SELECT {mapping} FROM daily_history WHERE date(time_label) BETWEEN date(?) AND date(?) ORDER BY time_label ASC"

        rows = conn.execute(query, (start_date, end_date)).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/limits')
def api_limits():
    conn = get_db_connection()
    if not conn: return jsonify({"error": "DB Link Down"}), 500
    row = conn.execute('SELECT MIN(time_label) as first_date FROM daily_history').fetchone()
    conn.close()
    return jsonify(dict(row))

if __name__ == '__main__':
    app.run(debug=True, port=5000)