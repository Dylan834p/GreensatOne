from flask import Flask
from api_routes import api_bp
from data_routes import data_bp
import threading
from data_services import ensure_schema, db_manager
threads = []

app = Flask(__name__)

app.register_blueprint(api_bp)
app.register_blueprint(data_bp)

def run_app():
    app.run(debug=True, port=5000)

if __name__ == '__main__':
    if not ensure_schema():
        print("Problem setting up database!")
        exit()

    t1 = threading.Thread(target=db_manager, daemon=True)
    t2 = threading.Thread(target=run_app)
    
    threads.append(t1)
    threads.append(t2)

    for t in threads:
        t.start()

    for t in threads:
        t.join()