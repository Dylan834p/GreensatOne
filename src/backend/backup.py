import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'greensat.db')

def clean_old_backups(max_files=20):
    backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")

    if not os.path.exists(backup_dir):
        return

    files = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")])

    while len(files) > max_files:
        os.remove(os.path.join(backup_dir, files[0]))
        files.pop(0)

def backup_db():
    backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"greensat_backup_{timestamp}.db")

    source = sqlite3.connect(DB_PATH)
    dest = sqlite3.connect(backup_file)

    with dest:
        source.backup(dest)

    source.close()
    dest.close()

    clean_old_backups(20)

    print(f"Backup created: {backup_file}")

if __name__ == "__main__":
    backup_db()