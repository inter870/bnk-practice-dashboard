# Deployment

This project is a Streamlit app.

Recommended production host: Streamlit Community Cloud or another Python web host that supports long-running Streamlit processes.

Entry point:

```text
app.py
```

Required secrets:

```text
DART_API_KEY
ECOS_API_KEY
OPENAI_API_KEY
BNK_VERIFY_SSL=false
```

Do not commit `.env`, `.streamlit/secrets.toml`, `data/`, `briefings/`, `__pycache__/`, or SQLite files.

Local verification:

```powershell
py -3.11 -m compileall app.py src tests
py -3.11 -m unittest discover tests
py -3.11 -m streamlit run app.py --server.port 8501
```

