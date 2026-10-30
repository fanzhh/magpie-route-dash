# Magpie Route Dash

Turn an old iPad into a Magpie routing stage — agents on top, Magpie hub in the middle, model grid below. A pigeon flies agent → hub → model with a colored berry when a route goes in-flight on Magpie `/trace`, then returns when the route completes.

## Requires

- Magpie gateway with live trace at `http://127.0.0.1:3425/v1/magpie/trace` (override via `MAGPIE_TRACE_URL`)
- Optional usage API at `http://127.0.0.1:3425/v1/magpie/usage/requests` (override via `MAGPIE_URL`)
- Python 3 (stdlib only)

## Run

```bash
python3 server.py
```

Then open `http://127.0.0.1:3431/` (on LAN, use your machine IP).

Env vars:

| Var | Default | Notes |
| --- | --- | --- |
| `DASH_HOST` | `0.0.0.0` | Bind address |
| `DASH_PORT` | `3431` | Dashboard port |
| `MAGPIE_URL` | local Magpie usage endpoint | Upstream usage API (`/api/routes`) |
| `MAGPIE_TRACE_URL` | local Magpie `/v1/magpie/trace` | Live in-flight routes (`/api/live`) |

## iPad mini 2 / iOS 12 Safari

ES5 JavaScript, no modern SPA stack — built to run on old Safari.

## Notes

- The tiny Python proxy strips `callerKeys` and similar secret-looking fields before serving the page.
- The pigeon SVG is original Magpie-inspired art (MIT), not extracted from Magpie.app.

## License

MIT — https://github.com/fanzhh/magpie-route-dash
