# API Choice

- **Étudiant** : Agathe
- **API choisie** : Frankfurter (taux de change)
- **URL base** : `https://api.frankfurter.dev/v1`
- **Documentation officielle** : https://frankfurter.dev/v1/
- **Auth** : None (aucune clé nécessaire)

## Endpoints testés

| Endpoint | Description | Exemple |
|---|---|---|
| `GET /v1/latest` | Derniers taux de change | `?base=EUR&symbols=USD,JPY` |
| `GET /v1/{date}` | Taux historiques | `/v1/2024-01-15?base=USD` |
| `GET /v1/currencies` | Liste des devises supportées | retourne `{"AUD":"Australian Dollar",...}` |

## Hypothèses de contrat (champs attendus, types, codes)

### `/v1/latest` et `/v1/{date}`
- **HTTP 200** avec `Content-Type: application/json`
- Corps JSON :
  - `amount` : float (valeur de base, défaut 1.0)
  - `base` : string (code ISO 4217, 3 lettres, ex: "EUR")
  - `date` : string (format YYYY-MM-DD)
  - `rates` : objet { string: float } — chaque taux est > 0
- Paramètres optionnels : `base` (devise de base), `symbols` (filtrer les devises cibles)

### `/v1/currencies`
- **HTTP 200** avec `Content-Type: application/json`
- Corps JSON : objet { string: string } — code ISO → nom complet

### Cas d'erreur attendus
- Devise inexistante (`?base=INVALID`) → HTTP 404 ou 422
- Date invalide (`/v1/9999-99-99`) → HTTP 404 ou 400
- Date trop ancienne (`/v1/1900-01-01`) → HTTP 404 ou 400

## Limites / rate limiting connu

- Pas de quotas mensuels/journaliers
- Rate-limiting anti-abus (pas de seuil documenté précisément)
- Taux mis à jour une fois par jour (~16h CET)

## Risques

- API gratuite, pas de SLA garanti
- Le domaine `api.frankfurter.app` redirige vers `api.frankfurter.dev/v1` (follow redirects nécessaire)
- Les taux du jour en cours peuvent changer si de nouvelles données sont publiées
- Pas de données le week-end/jours fériés (retourne le dernier jour ouvré)
