"""
runner.py — Exécute tous les tests et calcule les métriques QoS.

Un "run" = une exécution complète de la suite de tests.
Le runner produit un dict structuré prêt à être stocké en SQLite et affiché sur le dashboard.

Métriques QoS calculées :
  - latency_ms_avg : latence moyenne de tous les tests
  - latency_ms_p95 : 95e percentile de latence
  - error_rate     : proportion de tests FAIL (0.0 à 1.0)
  - availability   : proportion de tests PASS (= 1 - error_rate)
  - passed / failed / total : compteurs
"""

from datetime import datetime, timezone
from tester.client import FrankfurterClient
from tester.tests import ALL_TESTS


def _percentile(sorted_values, pct):
    """Calcule le percentile pct (0–100) sur une liste déjà triée."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    # Méthode nearest-rank
    idx = int(pct / 100 * n)
    idx = min(idx, n - 1)
    return sorted_values[idx]


def execute_run(client: FrankfurterClient = None) -> dict:
    """
    Lance tous les tests de ALL_TESTS et retourne un rapport complet.

    Retourne :
    {
        "api": "Frankfurter",
        "timestamp": "2026-04-20T14:30:00+00:00",
        "summary": {
            "total": 8,
            "passed": 7,
            "failed": 1,
            "error_rate": 0.125,
            "availability": 0.875,
            "latency_ms_avg": 210.3,
            "latency_ms_p95": 420.0
        },
        "tests": [
            {"name": "...", "status": "PASS", "latency_ms": 120.0, "details": ""},
            ...
        ]
    }
    """
    if client is None:
        client = FrankfurterClient()

    # ── Exécuter chaque test ─────────────────────────────────────────
    results = []
    for test_fn in ALL_TESTS:
        try:
            result = test_fn(client)
        except Exception as exc:
            # Si un test plante de façon inattendue, on le marque FAIL
            result = {
                "name": test_fn.__doc__ or test_fn.__name__,
                "status": "FAIL",
                "latency_ms": 0.0,
                "details": f"Exception: {exc}",
            }
        results.append(result)

    # ── Calculer les métriques QoS ───────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed

    latencies = sorted(r["latency_ms"] for r in results)
    latency_avg = sum(latencies) / total if total > 0 else 0.0
    latency_p95 = _percentile(latencies, 95)

    error_rate = failed / total if total > 0 else 0.0
    availability = passed / total if total > 0 else 0.0

    # ── Assembler le rapport ─────────────────────────────────────────
    return {
        "api": "Frankfurter",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "error_rate": round(error_rate, 3),
            "availability": round(availability, 3),
            "latency_ms_avg": round(latency_avg, 1),
            "latency_ms_p95": round(latency_p95, 1),
        },
        "tests": results,
    }