# src/metrics/db.py

import sqlite3
from pathlib import Path
from typing import List, Tuple
from src.config.settings import settings

DB_PATH = Path(__file__).resolve().parent.parent / "metrics.db"

def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_file TEXT NOT NULL,
            hw_accel BOOLEAN NOT NULL,
            time_seconds REAL NOT NULL,
            speed REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def insert_metric(video_file: str, hw_accel: bool, time_seconds: float, speed: float):
    """Insert a new metric into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO metrics (video_file, hw_accel, time_seconds, speed)
        VALUES (?, ?, ?, ?)
    ''', (video_file, hw_accel, time_seconds, speed))
    conn.commit()
    conn.close()

def get_latest_metrics(limit: int = 100) -> List[Tuple]:
    """Retrieve the latest metrics from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM metrics ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows
