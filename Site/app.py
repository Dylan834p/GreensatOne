from flask import Flask, render_template
import json
import os
import time

app = Flask(__name__)

# Chemin vers data.json (dossier parent)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, 'data.json')

def get_latest_data():
    try:
        # Si le fichier n'existe pas
        if not os.path.exists(JSON_PATH):
            return None
        
        # On lit le fichier
        with open(JSON_PATH, 'r') as f:
            return json.load(f)
    except:
        return None

@app.route('/')
def index():
    data = get_latest_data()
    return render_template('index.html', d=data)

if __name__ == '__main__':
    print("🚀 SITE LANCÉ ! Ne ferme pas cette fenêtre.")
    print("👉 Va sur http://127.0.0.1:5000")
    
    # C'EST ICI QUE LA MAGIE OPÈRE : use_reloader=False
    # Cela empêche le site de redémarrer en boucle quand le json change
    app.run(debug=True, port=5000, use_reloader=False)