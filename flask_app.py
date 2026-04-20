"""
flask_app.py — Application Flask principale.

Routes :
  /            → redirige vers /dashboard
  /run         → déclenche un run de tests et redirige vers /dashboard
  /dashboard   → affiche le dernier run + historique
  /health      → endpoint JSON pour monitoring (bonus)
  /export      → export JSON du dernier run (bonus)
"""

import json
from datetime import datetime, timezone
from flask import Flask, redirect, url_for, render_template, jsonify

from storage import init_db, save_run, list_runs, get_latest_run
from tester.runner import execute_run

# ── Initialisation ───────────────────────────────────────────────────
app = Flask(__name__)
init_db()

# ── Anti-spam : 1 run toutes les 60 secondes max ────────────────────
_last_run_time = None
RUN_COOLDOWN_SECONDS = 60


@app.route("/")
def index():
    """Redirige vers le dashboard."""
    return redirect(url_for("dashboard"))


@app.route("/run")
def run_tests():
    """
    Déclenche un run de tests, sauvegarde les résultats et redirige vers le dashboard.
    Inclut un mécanisme anti-spam (cooldown de 60s).
    """
    global _last_run_time

    now = datetime.now(timezone.utc)

    # Vérifier le cooldown
    if _last_run_time is not None:
        elapsed = (now - _last_run_time).total_seconds()
        if elapsed < RUN_COOLDOWN_SECONDS:
            # Trop tôt, on redirige sans exécuter
            return redirect(url_for("dashboard"))

    # Exécuter les tests
    report = execute_run()

    # Sauvegarder en base
    save_run(report)

    # Mettre à jour le timestamp anti-spam
    _last_run_time = now

    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    """Affiche le dashboard : dernier run détaillé + historique des runs."""
    latest = get_latest_run()
    history = list_runs(limit=20)
    return render_template("dashboard.html", latest=latest, history=history)


@app.route("/health")
def health():
    """
    Endpoint de santé (bonus).
    Retourne un JSON avec le statut global basé sur le dernier run.
    """
    latest = get_latest_run()

    if latest is None:
        return jsonify({
            "status": "unknown",
            "message": "No test run yet. Trigger one via /run",
        })

    # Déterminer le statut global
    availability = latest.get("availability", 0)
    if availability >= 0.9:
        status = "healthy"
    elif availability >= 0.5:
        status = "degraded"
    else:
        status = "unhealthy"

    return jsonify({
        "status": status,
        "api": latest.get("api", "Frankfurter"),
        "last_run": latest.get("timestamp", ""),
        "availability": availability,
        "latency_ms_avg": latest.get("latency_ms_avg", 0),
        "passed": latest.get("passed", 0),
        "failed": latest.get("failed", 0),
    })


@app.route("/export")
def export_json():
    """
    Export JSON du dernier run complet (bonus).
    Téléchargeable directement.
    """
    latest = get_latest_run()
    if latest is None:
        return jsonify({"error": "No test run yet"}), 404

    response = jsonify(latest)
    response.headers["Content-Disposition"] = "attachment; filename=latest_run.json"
    return response


# ── Lancement local (pas utilisé sur PythonAnywhere) ─────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)