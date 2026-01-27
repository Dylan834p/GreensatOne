from flask import Flask, render_template, jsonify, request
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

# Configuration des chemins
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'greensat.db')

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL;') # Mode rapide
        return conn
    except:
        return None

# --- PARTIE SITE WEB (INCHANGÉE) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def api_data():
    try:
        conn = get_db_connection()
        # On prend juste la toute dernière mesure reçue, peu importe le Pico
        row = conn.execute('SELECT * FROM mesures ORDER BY date_time DESC LIMIT 1').fetchone()
        conn.close()
        return jsonify(dict(row)) if row else (jsonify({"error": "Empty"}), 404)
    except:
        return jsonify({"error": "DB Error"}), 500

@app.route('/api/history')
def api_history():
    # Ton code historique existant (inchangé)
    try:
        start = request.args.get('start')
        end = request.args.get('end')
        conn = get_db_connection()
        query = "SELECT * FROM mesures WHERE date_time BETWEEN ? AND ? ORDER BY date_time ASC LIMIT 2000"
        rows = conn.execute(query, (start, end)).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except:
        return jsonify([])

@app.route('/api/limits')
def api_limits():
    try:
        conn = get_db_connection()
        row = conn.execute('SELECT MIN(date_time) as first_date, MAX(date_time) as last_date FROM mesures').fetchone()
        conn.close()
        return jsonify(dict(row))
    except: return jsonify({})

# --- NOUVELLE PARTIE : LE "BRIDGE" WIFI ---
@app.route('/api/upload', methods=['POST'])
def api_upload():
    try:
        # 1. On reçoit le paquet du Pico
        data = request.json
        pico_id = data.get("id", "Inconnu")
        
        # 2. On prépare la date et l'air
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        air_pct = data.get('air_pct', 0)
        
        # 3. On enregistre dans la Base de Données (Comme le faisait bridge.py avant)
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO mesures (date_time, temp, hum, gaz_pct, lux, press, air_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            now, 
            data.get('temp', 0), 
            data.get('hum', 0), 
            data.get('gaz_pct', 0), 
            data.get('lux', 0), 
            data.get('press', 0), 
            air_pct
        ))
        conn.commit()
        conn.close()

        # 4. AFFICHAGE DANS LA CONSOLE (C'est ça que tu veux voir !)
        # Cela remplace la fenêtre noire du bridge.py
        print(f"📡 [REÇU] {pico_id} : {data.get('temp')}°C | {data.get('hum')}%")
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"❌ Erreur Reception : {e}")
        return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    # On écoute sur 0.0.0.0 pour que les Picos puissent se connecter
    print("🚀 SERVEUR DÉMARRÉ (Mode Bridge Wifi)")
    print("👉 En attente des satellites GreenSat 1 & 2...")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)