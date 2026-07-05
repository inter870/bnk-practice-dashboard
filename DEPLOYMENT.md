# Deployment

This project is a Streamlit app. Entry point: `app.py`.

## 24-hour external access

`http://localhost:8501` is local only. For a public URL that stays reachable, deploy the repo to a web host and keep the app process alive.

Recommended options:

1. **Streamlit Community Cloud + keepalive monitor**
   - Use this for the easiest public URL.
   - Add all required secrets in Streamlit Cloud settings.
   - The included GitHub Action `.github/workflows/keepalive.yml` pings `https://stancedash.streamlit.app/` every 10 minutes.
   - For another URL, set GitHub repository variable `STREAMLIT_APP_URL`.
   - Community/free hosts can still cold-start or pause during platform maintenance.

2. **Render/Fly/Railway Docker deployment**
   - Use this for better 24-hour operation.
   - This repo now includes `Dockerfile`, `Procfile`, and `render.yaml`.
   - Choose a paid/non-sleeping plan for true always-on access.
   - Health check path: `/_stcore/health`.

## Required secrets

Set these in the hosting platform. Do not commit real values.

```text
DART_API_KEY
ECOS_API_KEY
OPENAI_API_KEY
KIS_APP_KEY
KIS_APP_SECRET
KIS_BASE_URL=https://openapi.koreainvestment.com:9443
BNK_VERIFY_SSL=false
```

The app now reads both environment variables and Streamlit Secrets.

## Streamlit Cloud checklist

1. Push this repo to GitHub.
2. Streamlit Cloud app settings:
   - Main file path: `app.py`
   - Python version: `runtime.txt` -> `python-3.11.8`
3. Add secrets in **App settings -> Secrets**:

```toml
DART_API_KEY = "..."
ECOS_API_KEY = "..."
OPENAI_API_KEY = "..."
KIS_APP_KEY = "..."
KIS_APP_SECRET = "..."
KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"
BNK_VERIFY_SSL = "false"
```

4. Confirm public health:

```text
https://stancedash.streamlit.app/_stcore/health
```

## Render Docker checklist

1. Create a Render Web Service from this repo.
2. Use the included `render.yaml` or choose Docker environment.
3. Set the required secrets in Render Environment.
4. Select a non-sleeping plan for real 24-hour service.
5. Health check path: `/_stcore/health`.

## Security

Do not commit `.env`, `.streamlit/secrets.toml`, `data/`, `briefings/`, `__pycache__/`, or SQLite files.

## Local verification

```powershell
py -3.11 -m compileall app.py src tests
py -3.11 -m unittest discover tests
py -3.11 -m streamlit run app.py --server.port 8501
```
