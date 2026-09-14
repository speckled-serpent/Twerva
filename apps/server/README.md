# Twerva server

FastAPI shell for the Twerva API. Health check only — no ingest, domain models, or publish loop yet.

Requires **Python 3.11+**.

## Run locally

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:application --reload --host 127.0.0.1 --port 8000
```

Alternatively, install from `pyproject.toml` with `pip install -e .` instead of `pip install -r requirements.txt`.

Check the process:

```bash
curl http://127.0.0.1:8000/health
```

Expected JSON:

```json
{"status":"ok"}
```

Interactive docs (FastAPI default): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
