# GreenSat Project

A multi-layered system designed for environmental monitoring, featuring a deployable station (sonde), a centralized backend, and a web-based visualization dashboard.

## 📂 Project Structure

* **documents/**: Project documentation, component lists (`composants.txt`), and 3D assets.
* **src/backend/**: Core logic for the base station, including the SQLite database (`greensat.db`) and data population scripts.
* **src/site/**: Flask-based web interface. Includes 3D model integration (GLB), custom CSS/JS, and HTML templates.
* **src/sonde/**: Firmware/scripts for the deployable hardware, handling GPS data and sensor telemetry.

## 🚀 Execution

### 1. Hardware (Sonde)

The station scripts are located in `src/sonde/`.

```bash
python src/sonde/main.py

```

### 2. Web Dashboard

The local web server and data visualization:

```bash
python src/site/app.py

```

**URL:** [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 🛠 Tech Stack

* **Backend**: Python, SQLite.
* **Frontend**: HTML5, CSS3, JavaScript (Three.js/Model-Viewer for 3D).
* **Hardware Interface**: Python-based sensor and GPS modules.

## 📝 Technical Notes

* **Database**: `greensat.db` updated via `bridge.py` and `populate_db.py`.
* **3D Assets**: Satellite model located in `src/site/static/models/`.

## 📡 Data Flow

1. **Sonde**: Collects telemetry and GPS data via `src/sonde/main.py`.
2. **Bridge**: Transfers raw hardware data to the backend.
3. **Database**: `src/backend/greensat.db` stores incoming metrics.
4. **Frontend**: `src/site/app.py` queries the database and renders data on the web interface.