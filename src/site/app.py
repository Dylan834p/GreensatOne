from flask import Flask
from api_routes import api_bp
from data_routes import data_bp

app = Flask(__name__)

app.register_blueprint(api_bp)
app.register_blueprint(data_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000)