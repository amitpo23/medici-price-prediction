# Azure Production Deployment

This project now includes CI/CD deployment via GitHub Actions:

- Workflow file: `.github/workflows/deploy-azure.yml`
- Target app name: `medici-prediction-api`

## 1) Configure GitHub Secret

In GitHub repository settings:

- `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`
- Name: `AZURE_WEBAPP_PUBLISH_PROFILE`
- Value: publish profile XML from Azure App Service

How to get publish profile:

- Azure Portal -> App Service `medici-prediction-api`
- `Get publish profile`
- Paste full XML into the GitHub secret above

## 2) Configure Azure App Settings

In Azure App Service -> `Configuration`, ensure:

- `SCM_DO_BUILD_DURING_DEPLOYMENT=true`
- `WEBSITES_PORT=8000`
- `PYTHONUNBUFFERED=1`

Required project env vars should also be present there (`MEDICI_DB_URL`, `PREDICTION_API_KEY`, etc.).

## 3) Startup Command

Startup script already exists in `startup.sh` and runs:

`gunicorn --bind 0.0.0.0:${PORT:-8000} -w 2 -k uvicorn.workers.UvicornWorker src.api.main:app --timeout 120`

Set App Service Startup Command to:

`bash startup.sh`

## 4) Deploy

Push to `main` (or run workflow manually via Actions UI).

After successful run, verify:

- `https://medici-prediction-api.azurewebsites.net/health`
- `https://medici-prediction-api.azurewebsites.net/api/v1/salesoffice/options`
