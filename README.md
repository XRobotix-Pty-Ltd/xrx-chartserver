# ChartServer

**Maintained by [XRobotix Pty Ltd](https://github.com/XRobotix-Pty-Ltd) (South Africa)**

A high-performance chart image rendering service. Drop-in compatible with the [QuickChart](https://quickchart.io/) API, extended with ECharts support, interactive embeds, and premium QR codes.

Licensed under **Apache 2.0**.

---

## Architecture

```
Public API (FastAPI, Python, port 8000)
    ↓ localhost:3401
Internal Renderer (Node.js — Chart.js + ECharts)
```

- Python owns the HTTP layer, QR codes, Graphviz, and interactive embeds
- Node.js handles all chart image rendering (Chart.js v2/v3/v4, ECharts v5)
- Single Docker container managed by `supervisord`

---

## Chart rendering

### Static image (PNG / SVG)

```
GET /chart?c={...}&format=png
POST /chart  {"chart": {...}, "format": "png"}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `c` | — | Chart config (Chart.js or ECharts JSON / JS expression) |
| `provider` | `chartjs` | `chartjs` or `echarts` |
| `format` | `png` | `png` or `svg` |
| `width` | `500` | Output width in pixels |
| `height` | `300` | Output height in pixels |
| `bkg` / `background` | — | Background colour (e.g. `white`, `#ffffff`) |
| `version` | `2` | Chart.js version: `2`, `3`, or `4` (chartjs provider only) |
| `devicePixelRatio` | `2.0` | Retina multiplier |

### Chart.js example

```
/chart?c={type:'bar',data:{labels:['Jan','Feb','Mar'],datasets:[{label:'Sales',data:[50,60,70]}]}}&bkg=white
```

Supports all standard Chart.js types plus:

| Type | Notes |
|------|-------|
| `sparkline` | Compact inline line chart |
| `progressBar` | Horizontal progress/stacked bar |
| `radialGauge` / `gauge` | Radial gauge (v2 only) |
| `boxplot`, `violin` | Statistical plots |
| `outlabeledPie`, `outlabeledDoughnut` | Pie with outside labels |
| `sankey` | Flow/Sankey diagrams (requires `version=3` or `version=4`) |

### ECharts example

```
/chart?provider=echarts&c={"series":[{"type":"sankey","data":[{"name":"A"},{"name":"B"}],"links":[{"source":"A","target":"B","value":5}]}]}&version=3
```

All [Apache ECharts](https://echarts.apache.org/) chart types are supported, including sankey, tree, sunburst, heatmap, graph, and more.

### Interactive embed

Returns a self-contained HTML page — no server-side rendering, zero overhead:

```
GET /chart/embed?provider=echarts&c={...}&width=600&height=400
```

Embed it in an `<iframe>` or serve directly.

---

## QR Codes

```
GET /qr?text=hello+world
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `text` | — | Data to encode (required) |
| `format` | `png` | `png`, `svg`, or `gif` |
| `size` | `300` | Output size in pixels |
| `dark` | `000000` | Dark module colour (hex, no `#`) |
| `light` | `ffffff` | Light module colour, or `transparent` |
| `style` | `square` | `square`, `rounded`, `circle`, `dots`, `bars`, `vbars` |
| `gradient` | — | `radial`, `horizontal`, `vertical`, `square` |
| `gradient_start` | `000000` | Gradient start colour |
| `gradient_end` | `4e78a7` | Gradient end colour |
| `eye_color` | — | Finder pattern corner colour |
| `logo` | — | Logo image URL or base64 data URI |
| `logo_size` | `0.3` | Logo as fraction of QR size (0.1–0.4) |
| `background` | — | Background image URL or base64 for artistic QR overlay |
| `error_correction` | `M` | `L`, `M`, `Q`, `H` (auto-upgrades to `H` when `logo` is set) |

### Premium QR examples

```bash
# Rounded modules with gradient
/qr?text=https://xrobotix.co.za&style=rounded&gradient=radial&gradient_start=003366&gradient_end=00AAFF

# Logo embedded in centre
/qr?text=https://xrobotix.co.za&logo=https://example.com/logo.png&logo_size=0.3

# Artistic QR with background image
/qr?text=https://xrobotix.co.za&background=https://example.com/bg.jpg

# SVG output
/qr?text=https://xrobotix.co.za&format=svg&dark=003366&light=transparent
```

---

## Graphviz

```
GET /graphviz?graph=digraph{A->B->C}
POST /graphviz  {"graph": "digraph { A -> B }", "format": "svg"}
```

Requires `graphviz` (`dot`) to be installed on the system.

---

## Health check

```
GET /healthcheck
→ {"success": true, "renderer": true, "version": "1.0.0"}
```

---

## Local development

No Docker required. Two terminals:

**Terminal 1 — Node.js renderer (port 3401):**
```bash
cd renderer
npm install
node index.js
```

**Terminal 2 — Python API (port 8000):**
```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then test:
```bash
curl "localhost:8000/healthcheck"
curl "localhost:8000/chart?c={type:'bar',data:{labels:['A','B'],datasets:[{data:[1,2]}]}}" --output chart.png
```

---

## Docker

### Build base image (system + language deps — rarely changes)

```bash
docker build -f Dockerfile.base -t xrobotix/xrx-chartserver:BASE_1 .
```

### Build application image

```bash
docker build -t xrobotix/xrx-chartserver:latest .
```

### Run

```bash
docker run -p 8000:8000 xrobotix/xrx-chartserver:latest
```

---

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push to `master` or `nightly`:

1. **docker-build-base** — rebuilds base image only when `Dockerfile.base` or dependency files change
2. **docker-build** — builds and pushes `xrobotix/xrx-chartserver:latest` (or `:branch`)
3. **docker-test** — runs `pytest` inside the built container
4. **trivy-scan** — Trivy CRITICAL/HIGH vulnerability scan (non-blocking)

PRs trigger build + test only (no push or deploy).

Required secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`

---

## Adding a new chart provider

1. Create `renderer/providers/myprovider.js` exporting `async render(config) → Buffer`
2. Register it in `renderer/index.js`: `const PROVIDERS = { chartjs, echarts, myprovider }`
3. Use it: `GET /chart?provider=myprovider&c={...}`

No changes to the Python layer needed.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

Copyright 2025 XRobotix Pty Ltd, South Africa.

Inspired by [typpo/quickchart](https://github.com/typpo/quickchart) (AGPL v3). This is an independent clean-room implementation.
