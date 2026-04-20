"""
client.py — Wrapper HTTP pour l'API Frankfurter.

Responsabilités :
  - Centraliser les appels HTTP (une seule session requests)
  - Mesurer la latence de chaque requête (en ms)
  - Gérer le timeout (3s par défaut)
  - Implémenter un retry simple (1 retry max) en cas d'erreur réseau ou 5xx
  - Gérer le rate-limiting (429) avec un backoff basique
"""

import time
import requests

# ── Configuration ────────────────────────────────────────────────────
BASE_URL = "https://api.frankfurter.dev/v1"
DEFAULT_TIMEOUT = 3          # secondes
MAX_RETRIES = 1              # 1 retry max (donc 2 tentatives au total)
BACKOFF_429 = 2              # secondes d'attente si on reçoit un 429


class APIResponse:
    """Encapsule la réponse HTTP + métadonnées de mesure."""

    def __init__(self, status_code, json_data, latency_ms, error=None):
        self.status_code = status_code    # int : code HTTP (ou 0 si erreur réseau)
        self.json_data = json_data        # dict | None : corps JSON parsé
        self.latency_ms = latency_ms      # float : durée de la requête en ms
        self.error = error                # str | None : message d'erreur éventuel

    @property
    def ok(self):
        """True si le code HTTP est 2xx."""
        return 200 <= self.status_code < 300

    def __repr__(self):
        return (
            f"APIResponse(status={self.status_code}, "
            f"latency={self.latency_ms:.0f}ms, "
            f"error={self.error})"
        )


class FrankfurterClient:
    """Client HTTP pour l'API Frankfurter avec timeout, retry et mesure."""

    def __init__(self, base_url=BASE_URL, timeout=DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Une session persistante = réutilisation des connexions TCP
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "API-Tester-Atelier/1.0",
        })

    # ── Méthode principale ───────────────────────────────────────────
    def get(self, path, params=None):
        """
        Effectue un GET sur base_url + path.

        Retourne un objet APIResponse contenant :
          - le status code
          - le JSON parsé (ou None)
          - la latence en ms
          - un éventuel message d'erreur

        En cas d'échec réseau ou de 5xx, retente une fois (MAX_RETRIES).
        En cas de 429, attend BACKOFF_429 secondes puis retente.
        """
        url = f"{self.base_url}/{path.lstrip('/')}" if path else self.base_url
        last_response = None

        for attempt in range(1 + MAX_RETRIES):
            try:
                start = time.monotonic()
                resp = self.session.get(url, params=params, timeout=self.timeout)
                latency_ms = (time.monotonic() - start) * 1000

                # ── Rate-limit : on attend puis on retente ───────────
                if resp.status_code == 429 and attempt < MAX_RETRIES:
                    time.sleep(BACKOFF_429)
                    continue

                # ── 5xx : on retente directement ─────────────────────
                if resp.status_code >= 500 and attempt < MAX_RETRIES:
                    continue

                # ── Tentative de parsing JSON ────────────────────────
                try:
                    json_data = resp.json()
                except ValueError:
                    json_data = None

                return APIResponse(
                    status_code=resp.status_code,
                    json_data=json_data,
                    latency_ms=latency_ms,
                )

            except requests.exceptions.Timeout:
                last_response = APIResponse(
                    status_code=0,
                    json_data=None,
                    latency_ms=self.timeout * 1000,
                    error="Timeout",
                )

            except requests.exceptions.ConnectionError as exc:
                last_response = APIResponse(
                    status_code=0,
                    json_data=None,
                    latency_ms=0,
                    error=f"ConnectionError: {exc}",
                )

            except requests.exceptions.RequestException as exc:
                last_response = APIResponse(
                    status_code=0,
                    json_data=None,
                    latency_ms=0,
                    error=f"RequestException: {exc}",
                )

        # Si on arrive ici, tous les retries ont échoué
        return last_response

    # ── Raccourcis pratiques pour chaque endpoint ─────────────────────
    def get_latest(self, base="EUR", symbols=None):
        """GET /v1/latest"""
        params = {"base": base}
        if symbols:
            params["symbols"] = symbols if isinstance(symbols, str) else ",".join(symbols)
        return self.get("latest", params=params)

    def get_historical(self, date, base="EUR", symbols=None):
        """GET /v1/{date}"""
        params = {"base": base}
        if symbols:
            params["symbols"] = symbols if isinstance(symbols, str) else ",".join(symbols)
        return self.get(date, params=params)

    def get_currencies(self):
        """GET /v1/currencies"""
        return self.get("currencies")