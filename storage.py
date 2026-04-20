"""
storage.py — Persistance des runs de tests en SQLite.

Deux tables :
  - runs     : un enregistrement par exécution (timestamp, métriques résumées)
  - results  : un enregistrement par test individuel, lié au run

Fonctions principales :
  - init_db()      : crée les tables si elles n'existent pas
  - save_run()     : persiste un rapport complet (run + résultats détaillés)
  - list_runs()    : retourne les N derniers runs (résumé uniquement)
  - get_run()      : retourne un run complet avec ses résultats détaillés
"""

import json
import os
import sqlite3

# ── Chemin de la base ────────────────────────────────────────────────
# Sur PythonAnywhere, le fichier sera à côté de flask_app.py
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_runs.db")


def _connect():
    """Ouvre une connexion SQLite avec Row factory pour accès par nom de colonne."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée les tables si elles n'existent pas encore."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            api             TEXT NOT NULL,
            timestamp       TEXT NOT NULL,
            total           INTEGER NOT NULL,
            passed          INTEGER NOT NULL,
            failed          INTEGER NOT NULL,
            error_rate      REAL NOT NULL,
            availability    REAL NOT NULL,
            latency_ms_avg  REAL NOT NULL,
            latency_ms_p95  REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      INTEGER NOT NULL,
            name        TEXT NOT NULL,
            status      TEXT NOT NULL,
            latency_ms  REAL NOT NULL,
            details     TEXT DEFAULT '',
            FOREIGN KEY (run_id) REFERENCES runs(id)
        )
    """)

    conn.commit()
    conn.close()


def save_run(report: dict) -> int:
    """
    Persiste un rapport de run complet en base.

    Paramètre : le dict retourné par runner.execute_run()
    Retourne  : l'id du run inséré
    """
    conn = _connect()
    cursor = conn.cursor()

    summary = report["summary"]

    cursor.execute("""
        INSERT INTO runs (api, timestamp, total, passed, failed,
                          error_rate, availability, latency_ms_avg, latency_ms_p95)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        report["api"],
        report["timestamp"],
        summary["total"],
        summary["passed"],
        summary["failed"],
        summary["error_rate"],
        summary["availability"],
        summary["latency_ms_avg"],
        summary["latency_ms_p95"],
    ))

    run_id = cursor.lastrowid

    for test in report["tests"]:
        cursor.execute("""
            INSERT INTO results (run_id, name, status, latency_ms, details)
            VALUES (?, ?, ?, ?, ?)
        """, (
            run_id,
            test["name"],
            test["status"],
            test["latency_ms"],
            test.get("details", ""),
        ))

    conn.commit()
    conn.close()
    return run_id


def list_runs(limit=20) -> list:
    """
    Retourne les N derniers runs (résumé uniquement), du plus récent au plus ancien.

    Retourne une liste de dicts :
    [
        {"id": 42, "api": "Frankfurter", "timestamp": "...", "passed": 8, "failed": 0, ...},
        ...
    ]
    """
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, api, timestamp, total, passed, failed,
               error_rate, availability, latency_ms_avg, latency_ms_p95
        FROM runs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    runs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return runs


def get_run(run_id: int) -> dict | None:
    """
    Retourne un run complet (résumé + résultats détaillés) par son id.

    Retourne None si le run n'existe pas.
    """
    conn = _connect()
    cursor = conn.cursor()

    # Récupérer le run
    cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    run = dict(row)

    # Récupérer les résultats associés
    cursor.execute("""
        SELECT name, status, latency_ms, details
        FROM results
        WHERE run_id = ?
        ORDER BY id
    """, (run_id,))

    run["tests"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return run


def get_latest_run() -> dict | None:
    """Raccourci : retourne le dernier run complet, ou None si aucun run."""
    runs = list_runs(limit=1)
    if not runs:
        return None
    return get_run(runs[0]["id"])