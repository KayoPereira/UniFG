from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_code TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                department TEXT,
                face_embedding TEXT NOT NULL,
                photo_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attendance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                recognized_at TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL DEFAULT 'camera',
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            );

            CREATE INDEX IF NOT EXISTS idx_attendance_logs_employee_id
            ON attendance_logs(employee_id);

            CREATE INDEX IF NOT EXISTS idx_attendance_logs_recognized_at
            ON attendance_logs(recognized_at DESC);
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def serialize_embedding(embedding: np.ndarray) -> str:
    return json.dumps(embedding.astype(float).tolist())


def deserialize_embedding(raw_value: str) -> np.ndarray:
    return np.array(json.loads(raw_value), dtype=np.float32)


def employee_exists(employee_code: str) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM employees WHERE employee_code = ?",
            (employee_code,),
        ).fetchone()
    return row is not None


def create_employee(
    employee_code: str,
    full_name: str,
    department: str | None,
    face_embedding: np.ndarray,
    photo_path: Path | None,
) -> dict[str, Any]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO employees (
                employee_code,
                full_name,
                department,
                face_embedding,
                photo_path,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                employee_code,
                full_name,
                department,
                serialize_embedding(face_embedding),
                str(photo_path) if photo_path else None,
                utc_now_iso(),
            ),
        )
        employee_id = cursor.lastrowid
        row = connection.execute(
            "SELECT * FROM employees WHERE id = ?",
            (employee_id,),
        ).fetchone()
    return row_to_dict(row) or {}


def list_employees() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM employees ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def list_employee_embeddings() -> list[dict[str, Any]]:
    employees = list_employees()
    for employee in employees:
        employee["face_embedding"] = deserialize_embedding(employee["face_embedding"])
    return employees


def create_attendance_log(
    employee_id: int,
    confidence: float,
    source: str = "camera",
) -> dict[str, Any]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO attendance_logs (
                employee_id,
                recognized_at,
                confidence,
                source
            ) VALUES (?, ?, ?, ?)
            """,
            (employee_id, utc_now_iso(), confidence, source),
        )
        row = connection.execute(
            "SELECT * FROM attendance_logs WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return row_to_dict(row) or {}


def list_attendance_logs(limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT attendance_logs.*, employees.employee_code, employees.full_name
            FROM attendance_logs
            INNER JOIN employees ON employees.id = attendance_logs.employee_id
            ORDER BY attendance_logs.recognized_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_dashboard_metrics() -> dict[str, int]:
    with get_connection() as connection:
        employees_count = connection.execute(
            "SELECT COUNT(*) FROM employees"
        ).fetchone()[0]
        attendance_count = connection.execute(
            "SELECT COUNT(*) FROM attendance_logs"
        ).fetchone()[0]
    return {
        "employees_count": employees_count,
        "attendance_count": attendance_count,
    }
