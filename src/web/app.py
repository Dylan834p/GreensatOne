from flask import Flask
from routes.api_routes import api_bp
from routes.data_routes import data_bp
import threading
from services.data_services import ensure_schema, db_manager
threads = []

app = Flask(__name__)

app.register_blueprint(api_bp)
app.register_blueprint(data_bp)

if __name__ == '__main__':
    if not ensure_schema():
        exit()
    threading.Thread(target=db_manager, daemon=True).start()

    app.run(host='0.0.0.0', port=5000, debug=False)