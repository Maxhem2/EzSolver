<div align="center">

<h1>⚡ EzSolver</h1>

<p><strong>Fast, cross-platform Cloudflare Turnstile solver powered by headless Chrome.</strong><br/>
No paid APIs. No third-party services. Just Python and Chrome.</p>

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey?style=flat-square)]()
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)]()
[![Made by](https://img.shields.io/badge/Made%20by-Ismoiloff-orange?style=flat-square)](https://github.com/ismoiloffS)

</div>

---

## How it works

EzSolver injects a Turnstile widget directly into the target page using Chrome through [SeleniumBase CDP Mode](https://seleniumbase.io/examples/cdp_mode/ReadMe/). It uses SeleniumBase's asynchronous CDP driver, so page scripts and mouse input work without a visible browser window.

- **Invisible widgets** resolve automatically within seconds
- **Managed (checkbox) widgets** are clicked with human-like mouse movement
- **True headless Chrome is the default** on Windows and Linux
- Optional Xvfb compatibility mode is available on Linux for sites that behave differently in true headless mode
- Every solve uses an isolated temporary Chrome profile, including concurrent service workers
- Chrome path and profile parent directory are auto-detected per OS, with environment variable overrides

---

## Requirements

- Python **3.9+**
- Google Chrome installed
- `seleniumbase` Python package (the tested version is pinned in `requirements.txt`)
- **Optional on Linux:** `Xvfb` for compatibility mode

---

## Installation

**1. Clone the repo**

```bash
git clone https://github.com/ismoiloffS/EzSolver.git
cd EzSolver
```

**2. Install the pinned Python dependency**

```bash
pip install -r requirements.txt
```

True headless mode needs no display server. To use the optional Linux Xvfb
compatibility mode, install Xvfb:

```bash
sudo apt install xvfb
```

> Windows users: nothing extra is needed; Chrome runs headlessly by default.

---

## Usage

### Option A — Standalone solver (single token)

Run `solver.py` directly from the command line:

```bash
python solver.py <sitekey> <siteurl>
```

**Example:**

```bash
python solver.py 0x4AAAAAAActoBfh_En8yr3T https://example.com/
```

**Output:**

```
[solver] clicking Cloudflare iframe at (48, 52)
0.abc123...longtoken...xyz
```

---

### Option B — Local API service

Start `service.py` once and send as many solve requests as you want via HTTP.

**Start the service:**

```bash
python service.py
```

```
[service] Turnstile solver service running on http://0.0.0.0:8191
```

**Send a request with the CLI client:**

```bash
python clientsend.py <sitekey> <siteurl> [timeout]
```

```bash
python clientsend.py 0x4AAAAAAActoBfh_En8yr3T https://example.com/
```

```
Token (14.32s): 0.abc123...longtoken...xyz
```

**Or call it from your own code / any HTTP client:**

```bash
curl -s -X POST http://127.0.0.1:8191/solve \
  -H "Content-Type: application/json" \
  -d '{"sitekey":"0x4AAAAAAActoBfh_En8yr3T","siteurl":"https://example.com/"}'
```

```json
{
  "token": "0.abc123...longtoken...xyz",
  "elapsed": 14.32
}
```

**Use it from Python:**

```python
from clientsend import request_token

token, elapsed = request_token(
    sitekey="0x4AAAAAAActoBfh_En8yr3T",
    siteurl="https://example.com/"
)
print(f"Got token in {elapsed}s: {token}")
```

---

## API reference

### `POST /solve`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `sitekey` | string | yes | — | Turnstile sitekey from the target page |
| `siteurl` | string | yes | — | Full URL of the page with the Turnstile widget |
| `timeout` | integer | no | `45` | Max seconds to wait for a token |

**Success response `200`:**
```json
{ "token": "0.abc...", "elapsed": 12.5 }
```

**Error response `500`:**
```json
{ "error": "Turnstile token not obtained within 45s" }
```

### `GET /health`

Returns current service status — useful for uptime checks and monitoring queue depth.

```json
{ "status": "ok", "workers": 4, "active": 2, "queued": 5 }
```

---

## Scaling

EzSolver uses a **worker pool** to handle high volumes safely. Instead of spinning up unlimited Chrome instances (which would crash your machine), requests queue up and are processed as workers free up — no requests are dropped.

```
500 requests → queue → [worker 1] [worker 2] [worker 3] [worker 4] → tokens
```

**Rule of thumb:** each Chrome worker uses ~500 MB RAM.

| Machine RAM | Recommended `MAX_WORKERS` | Throughput (est.) |
|-------------|--------------------------|-------------------|
| 2 GB | 2 | ~8 tokens/min |
| 4 GB | 4 (default) | ~16 tokens/min |
| 8 GB | 8 | ~32 tokens/min |
| 16 GB+ | 16 | ~64 tokens/min |

Set `MAX_WORKERS` when starting the service:

```bash
MAX_WORKERS=8 python service.py
```

Check the queue live via `/health`:

```bash
curl http://127.0.0.1:8191/health
```

```json
{ "status": "ok", "workers": 8, "active": 6, "queued": 47 }
```

For truly massive scale (thousands of concurrent solves), run **multiple service instances** behind a load balancer (nginx, Caddy, etc.) across several machines.

---

## Configuration

| Environment variable | Default | Description |
|----------------------|---------|-------------|
| `CHROME_PATH` | auto-detected | Path to your Chrome executable |
| `TS_PROFILE_DIR` | system temp + `ezsolver_profiles` | Parent directory for isolated temporary worker profiles |
| `TRUE_HEADLESS` | `1` | Run Chrome in true headless mode (`0` enables a visible browser) |
| `USE_XVFB` | `0` | On Linux, use headed Chrome under Xvfb instead of true headless mode |
| `PORT` | `8191` | Port the service listens on |
| `MAX_WORKERS` | `4` | Max concurrent Chrome instances |

**Examples:**
```bash
MAX_WORKERS=8 PORT=9000 python service.py

# Linux compatibility fallback for a site that fails in true headless mode
USE_XVFB=1 python service.py
```

---

## Project structure

```
EzSolver/
├── solver.py      # Core solver — browser automation logic
├── service.py     # HTTP API wrapper around the solver
└── clientsend.py  # CLI client + importable helper for service.py
```

---

## Troubleshooting

**Chrome not found**
> Set `CHROME_PATH` to the full path of your Chrome executable.

**Timeout / token not received**
> The target site may be serving a harder challenge. Try increasing the timeout: `python clientsend.py <key> <url> 90`

**A widget behaves differently in true headless mode (Linux)**
> Install Xvfb with `sudo apt install xvfb`, then start with `USE_XVFB=1 python service.py`.

---

<div align="center">

Made with ☕ by [Ismoiloff](https://github.com/ismoiloffS)

</div>
