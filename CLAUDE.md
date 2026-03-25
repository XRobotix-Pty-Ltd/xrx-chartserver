# CLAUDE.md — ChartServer

## Project overview

ChartServer is an Apache 2.0 chart image rendering service maintained by **XRobotix Pty Ltd (South Africa)**. It is a clean-room rewrite, not a fork of any AGPL codebase.

**Architecture:**
- `api/` — Python FastAPI (port 8000, public-facing)
- `renderer/` — Node.js Express (port 3401, internal only)
- Single Docker container via `supervisord`

---

## Development setup (no Docker)

Two terminals required:

```bash
# Terminal 1
cd renderer && node index.js

# Terminal 2
cd api && uvicorn main:app --reload --port 8000
```

---

## Key conventions

### Python API (`api/`)

- Routes live in `api/routes/` — one file per endpoint group
- `rendering_client.py` owns all communication with the Node.js renderer
- Use `async def` everywhere — FastAPI is fully async
- `httpx.AsyncClient` is reused across requests via a module-level singleton in `rendering_client.py`
- Do not import from `renderer/` — the boundary is HTTP only

### Node.js renderer (`renderer/`)

- Each chart provider is a file in `renderer/providers/` exporting `async render(config) → Buffer`
- `config` always contains: `{ chart, format, width, height, backgroundColor, devicePixelRatio, version }`
- `renderer/index.js` dispatches to providers — add new providers there only
- Never expose the renderer port (3401) outside the container

### Chart config parsing

- The renderer accepts chart configs as either a plain JSON object or a JS expression string
- JS string evaluation is intentional — it supports gradient helpers and pattern fills
- The Python API passes the config through as-is (string or parsed JSON object)

---

## Adding a new chart provider

1. Create `renderer/providers/myprovider.js`:
   ```js
   async function render(config) {
     // config: { chart, format, width, height, backgroundColor, ... }
     // return: Buffer (PNG or SVG)
   }
   module.exports = { render };
   ```
2. Register in `renderer/index.js`:
   ```js
   const myprovider = require('./providers/myprovider');
   const PROVIDERS = { chartjs, echarts, myprovider };
   ```
3. Call via API: `GET /chart?provider=myprovider&c={...}`

No Python changes needed.

---

## QR code notes

- PNG output uses `qrcode` (MIT) with `StyledPilImage` for shapes and gradients
- SVG output uses `segno` (BSD-3)
- Artistic / GIF output uses `segno` + `qrcode-artistic` (MIT)
- GPL libraries (`amazing-qr`, `MyQR`) are **excluded** — they are incompatible with Apache 2.0
- When `logo` param is present, error correction auto-upgrades to `H` (30% recovery)

---

## Docker

- `Dockerfile.base` — system deps (Python, Node.js, Cairo, Pango, Graphviz). Rebuilt only when base deps change.
- `Dockerfile` — app code layer. Rebuilt on every commit.
- Base image tag is currently `BASE_1`. Increment to `BASE_2` etc. when `Dockerfile.base` changes.
- Both services start via `supervisord.conf` — renderer starts first (priority 10), API second (priority 20)

---

## CI/CD

GitHub Actions workflow: `.github/workflows/ci.yml`

- Runs on push to `master` / `nightly`
- Self-hosted runners
- Secrets required: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`
- SonarQube is intentionally excluded
- Trivy scan is `continue-on-error: true` (non-blocking)

---

## License

Apache 2.0. All dependencies are MIT, Apache 2.0, BSD-3, or ISC.
Do not add GPL or AGPL dependencies.

---

## XRobotix context

- Company: XRobotix Pty Ltd, South Africa (ZA/RSA)
- Python is the primary language — keep the Python layer clean and idiomatic
- Performance matters: this service renders high volumes of charts
- The Node.js renderer is a necessary dependency for Chart.js/ECharts — it is internal and not user-facing
