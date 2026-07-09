# Environment And Secret Loading

The Streamlit dashboard loads API keys through the central module `src/config/env.py`.

## Loading Priority

1. Existing `os.environ`
2. Streamlit Cloud / `.streamlit/secrets.toml` through `st.secrets`
3. `ENV_FILE_PATH`
4. `APP_ENV_FILE`
5. `DOTENV_CONFIG_PATH`
6. Default local external file: `C:\Users\BNKFN\Desktop\bnk_practice\.env`
7. Project root `.env.local`
8. Project root `.env`
9. Project root `.streamlit/secrets.toml` as a non-Streamlit fallback

File-based values are loaded with override disabled. Values already injected by the deployment platform are not overwritten by local files.

## Supported Aliases

DART / OpenDART:

- `DART_API_KEY`
- `OPENDART_API_KEY`
- `OPEN_DART_API_KEY`

BOK ECOS:

- `ECOS_API_KEY`
- `ECOS_AUTH_KEY`
- `BOK_ECOS_API_KEY`
- `BANK_OF_KOREA_API_KEY`

## Local Run

PowerShell:

```powershell
$env:ENV_FILE_PATH="C:\Users\BNKFN\Desktop\bnk_practice\.env"
streamlit run app.py
```

Check secret availability without printing secret values:

```powershell
python scripts/check_env.py
```

## Streamlit Community Cloud

Paste the same key names into the app's Cloud Secrets manager. You can use TOML format:

```toml
OPENDART_API_KEY = "..."
BOK_ECOS_API_KEY = "..."
OPENAI_API_KEY = "..."
```

Do not commit `.streamlit/secrets.toml`.

## Render / Railway / EC2 / Docker / NAS

Preferred: inject environment variables directly in the platform settings.

Alternative: mount a secret file and point the app to it:

```powershell
$env:ENV_FILE_PATH="D:\secure\stance-dashboard\.env"
streamlit run app.py
```

For Docker, mount the file read-only and set `ENV_FILE_PATH`:

```bash
docker run --env ENV_FILE_PATH=/run/secrets/dashboard.env -v /host/secure/dashboard.env:/run/secrets/dashboard.env:ro stance-dashboard
```

## Safety Rules

- Never print or log raw API keys.
- Never commit `.env`, `.env.*`, `secrets.toml`, or `.streamlit/secrets.toml`.
- If a required key is missing, ECOS/DART requests should not be attempted.
- API failure, missing key, parsing failure, and empty response should be treated as different states in UI messaging.
