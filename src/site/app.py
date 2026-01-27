from flask import Flask, render_template, jsonify, request
import sqlite3
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'greensat.db')

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except:
        return None

@app.route('/')
def index():
    return render_template('index.html')

# API TEMPS RÉEL (Dernière valeur)
@app.route('/api/data')
def api_data():
    try:
        conn = get_db_connection()
        row = conn.execute('SELECT * FROM mesures ORDER BY date_time DESC LIMIT 1').fetchone()
        conn.close()
        return jsonify(dict(row)) if row else (jsonify({"error": "Empty"}), 404)
    except:
        return jsonify({"error": "DB Error"}), 500

@app.after_request
def add_header(response):
    # Cache les fichiers statiques (images, 3d, css) pendant 1 semaine (604800s)
    if request.path.startswith('/static'):
        response.headers['Cache-Control'] = 'public, max-age=604800'
    return response

# API HISTORIQUE (OPTIMISÉE DOWNSAMPLING)
@app.route('/api/history')
def api_history():
    try:
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        mode = request.args.get('mode', 'day') # On récupère le mode pour optimiser
        
        conn = get_db_connection()
        
        if not start_date or not end_date:
            # Fallback par défaut (100 derniers points)
            rows = conn.execute("SELECT * FROM (SELECT * FROM mesures ORDER BY date_time DESC LIMIT 100) ORDER BY date_time ASC").fetchall()
            conn.close()
            return jsonify([dict(row) for row in rows])

        # --- LOGIQUE D'OPTIMISATION SQL (LE SECRET DE LA PERF) ---
        if mode == 'year':
            # VUE ANNÉE : Moyenne par JOUR
            # Réduit ~9000 points -> 365 points (Facteur 25x)
            query = """
            SELECT 
                strftime('%Y-%m-%d 12:00:00', date_time) as date_time,
                ROUND(AVG(temp), 1) as temp,
                CAST(AVG(hum) AS INTEGER) as hum,
                ROUND(AVG(gaz_pct), 2) as gaz_pct,
                CAST(AVG(lux) AS INTEGER) as lux,
                ROUND(AVG(press), 1) as press
            FROM mesures 
            WHERE date_time BETWEEN ? AND ?
            GROUP BY strftime('%Y-%m-%d', date_time)
            ORDER BY date_time ASC
            """
            rows = conn.execute(query, (start_date, end_date)).fetchall()

        elif mode == 'month':
            # VUE MOIS : Moyenne par tranche de 4 HEURES
            # Réduit ~3000 points -> ~180 points (Facteur 16x)
            query = """
            SELECT 
                datetime((strftime('%s', date_time) / 14400) * 14400, 'unixepoch') as date_time,
                ROUND(AVG(temp), 1) as temp,
                CAST(AVG(hum) AS INTEGER) as hum,
                ROUND(AVG(gaz_pct), 2) as gaz_pct,
                CAST(AVG(lux) AS INTEGER) as lux,
                ROUND(AVG(press), 1) as press
            FROM mesures 
            WHERE date_time BETWEEN ? AND ?
            GROUP BY (strftime('%s', date_time) / 14400)
            ORDER BY date_time ASC
            """
            rows = conn.execute(query, (start_date, end_date)).fetchall()

        else:
            # VUE SEMAINE / JOUR : Données Brutes (Précision Max)
            # On limite quand même à 2000 points par sécurité
            query = "SELECT * FROM mesures WHERE date_time BETWEEN ? AND ? ORDER BY date_time ASC LIMIT 2000"
            rows = conn.execute(query, (start_date, end_date)).fetchall()
            
        conn.close()
        return jsonify([dict(row) for row in rows])

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# API LIMITES (Pour savoir quand cacher les flèches)
@app.route('/api/limits')
def api_limits():
    try:
        conn = get_db_connection()
        row = conn.execute('SELECT MIN(date_time) as first_date, MAX(date_time) as last_date FROM mesures').fetchone()
        conn.close()
        return jsonify(dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Dans app.py (fonction get_db_connection)
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # AJOUTER CETTE LIGNE :
        conn.execute('PRAGMA journal_mode=WAL;') 
        return conn
    except:
        return None
    

if __name__ == '__main__':
    print("🚀 Serveur lancé sur http://127.0.0.1:5000")
    app.run(debug=True, port=5000)