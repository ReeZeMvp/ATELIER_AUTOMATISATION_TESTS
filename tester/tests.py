"""
tests.py — Fonctions de test pour l'API Frankfurter.

Chaque fonction de test :
  - Reçoit un FrankfurterClient en paramètre
  - Retourne un dict {"name": str, "status": "PASS"|"FAIL", "latency_ms": float, "details": str}

Organisation :
  A. Tests Contrat (fonctionnels) — vérifient que l'API respecte son contrat
  B. Tests Robustesse — vérifient le comportement face à des entrées invalides
"""

from tester.client import FrankfurterClient


def _result(name, passed, latency_ms, details=""):
    """Fabrique un dict de résultat standardisé."""
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "latency_ms": round(latency_ms, 1),
        "details": details,
    }


# ═══════════════════════════════════════════════════════════════════════
# A. TESTS CONTRAT (fonctionnels)
# ═══════════════════════════════════════════════════════════════════════

def test_latest_status_ok(client: FrankfurterClient) -> dict:
    """Test 1 — GET /latest retourne HTTP 200."""
    resp = client.get_latest()
    return _result(
        name="GET /latest → HTTP 200",
        passed=resp.status_code == 200,
        latency_ms=resp.latency_ms,
        details=f"Got status {resp.status_code}" if resp.status_code != 200 else "",
    )


def test_latest_content_type(client: FrankfurterClient) -> dict:
    """Test 2 — La réponse de /latest est bien du JSON (Content-Type)."""
    resp = client.get_latest()
    # On vérifie via le parsing : si json_data est None, ce n'est pas du JSON
    is_json = resp.json_data is not None
    return _result(
        name="GET /latest → Content-Type JSON",
        passed=is_json,
        latency_ms=resp.latency_ms,
        details="" if is_json else "Response body is not valid JSON",
    )


def test_latest_required_fields(client: FrankfurterClient) -> dict:
    """Test 3 — /latest contient les champs obligatoires : amount, base, date, rates."""
    resp = client.get_latest()
    if not resp.json_data:
        return _result("GET /latest → champs obligatoires", False, resp.latency_ms, "No JSON body")

    required = {"amount", "base", "date", "rates"}
    present = set(resp.json_data.keys())
    missing = required - present

    return _result(
        name="GET /latest → champs obligatoires",
        passed=len(missing) == 0,
        latency_ms=resp.latency_ms,
        details=f"Missing: {missing}" if missing else "",
    )


def test_latest_field_types(client: FrankfurterClient) -> dict:
    """Test 4 — Les types des champs de /latest sont corrects."""
    resp = client.get_latest()
    if not resp.json_data:
        return _result("GET /latest → types des champs", False, resp.latency_ms, "No JSON body")

    data = resp.json_data
    errors = []

    # amount doit être un nombre (int ou float)
    if not isinstance(data.get("amount"), (int, float)):
        errors.append(f"amount: expected number, got {type(data.get('amount')).__name__}")

    # base doit être une string de 3 lettres
    base = data.get("base")
    if not isinstance(base, str) or len(base) != 3:
        errors.append(f"base: expected 3-letter string, got {base!r}")

    # date doit être une string au format YYYY-MM-DD
    date = data.get("date")
    if not isinstance(date, str) or len(date) != 10:
        errors.append(f"date: expected YYYY-MM-DD string, got {date!r}")

    # rates doit être un dict avec des valeurs float > 0
    rates = data.get("rates")
    if not isinstance(rates, dict):
        errors.append(f"rates: expected dict, got {type(rates).__name__}")
    elif rates:
        # Vérifier quelques valeurs
        for currency, rate in list(rates.items())[:5]:
            if not isinstance(rate, (int, float)) or rate <= 0:
                errors.append(f"rates[{currency}]: expected positive number, got {rate!r}")

    return _result(
        name="GET /latest → types des champs",
        passed=len(errors) == 0,
        latency_ms=resp.latency_ms,
        details="; ".join(errors) if errors else "",
    )


def test_latest_symbols_filter(client: FrankfurterClient) -> dict:
    """Test 5 — Le paramètre symbols filtre bien les devises retournées."""
    resp = client.get_latest(base="EUR", symbols=["USD", "JPY"])
    if not resp.json_data or "rates" not in resp.json_data:
        return _result("GET /latest?symbols=USD,JPY → filtrage", False, resp.latency_ms, "No rates in response")

    rates = resp.json_data["rates"]
    expected_keys = {"USD", "JPY"}
    actual_keys = set(rates.keys())

    passed = actual_keys == expected_keys
    details = ""
    if not passed:
        details = f"Expected {expected_keys}, got {actual_keys}"

    return _result(
        name="GET /latest?symbols=USD,JPY → filtrage",
        passed=passed,
        latency_ms=resp.latency_ms,
        details=details,
    )


def test_currencies_returns_dict(client: FrankfurterClient) -> dict:
    """Test 6 — /currencies retourne un dict {code: nom} non vide."""
    resp = client.get_currencies()
    if not resp.json_data:
        return _result("GET /currencies → dict non vide", False, resp.latency_ms, "No JSON body")

    data = resp.json_data
    is_valid = isinstance(data, dict) and len(data) > 10  # on attend au moins une dizaine de devises

    errors = []
    if not isinstance(data, dict):
        errors.append(f"Expected dict, got {type(data).__name__}")
    elif len(data) <= 10:
        errors.append(f"Expected >10 currencies, got {len(data)}")
    else:
        # Vérifier que les clés sont des strings de 3 lettres
        sample = list(data.items())[:3]
        for code, name in sample:
            if not isinstance(code, str) or len(code) != 3:
                errors.append(f"Key {code!r} is not a 3-letter code")
            if not isinstance(name, str) or len(name) == 0:
                errors.append(f"Value for {code} is not a non-empty string")

    return _result(
        name="GET /currencies → dict non vide",
        passed=len(errors) == 0,
        latency_ms=resp.latency_ms,
        details="; ".join(errors) if errors else "",
    )


# ═══════════════════════════════════════════════════════════════════════
# B. TESTS ROBUSTESSE (non-fonctionnels)
# ═══════════════════════════════════════════════════════════════════════

def test_invalid_currency_returns_error(client: FrankfurterClient) -> dict:
    """Test 7 — Une devise invalide retourne un code d'erreur (pas un 200)."""
    resp = client.get_latest(base="INVALID")
    # On attend un 404 ou 422, en tout cas PAS un 200
    passed = resp.status_code in (400, 404, 422)
    return _result(
        name="GET /latest?base=INVALID → erreur attendue",
        passed=passed,
        latency_ms=resp.latency_ms,
        details=f"Got status {resp.status_code}" if not passed else "",
    )


def test_invalid_date_returns_error(client: FrankfurterClient) -> dict:
    """Test 8 — Une date invalide retourne un code d'erreur."""
    resp = client.get_historical("9999-99-99")
    passed = resp.status_code in (400, 404, 422)
    return _result(
        name="GET /9999-99-99 → erreur attendue",
        passed=passed,
        latency_ms=resp.latency_ms,
        details=f"Got status {resp.status_code}" if not passed else "",
    )


# ═══════════════════════════════════════════════════════════════════════
# REGISTRE : liste ordonnée de tous les tests à exécuter
# ═══════════════════════════════════════════════════════════════════════

ALL_TESTS = [
    test_latest_status_ok,           # 1 — Contrat : HTTP 200
    test_latest_content_type,        # 2 — Contrat : JSON valide
    test_latest_required_fields,     # 3 — Contrat : champs obligatoires
    test_latest_field_types,         # 4 — Contrat : types corrects
    test_latest_symbols_filter,      # 5 — Contrat : filtrage symbols
    test_currencies_returns_dict,    # 6 — Contrat : /currencies
    test_invalid_currency_returns_error,  # 7 — Robustesse : devise invalide
    test_invalid_date_returns_error,      # 8 — Robustesse : date invalide
]