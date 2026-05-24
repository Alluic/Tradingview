# Deployment

Target repo: `https://github.com/Alluic/Tradingview`

## Dashboard Hosting

Host the dashboard with Streamlit Community Cloud:

1. Push this project to `Alluic/Tradingview`.
2. Go to `https://share.streamlit.io`.
3. Create a new app from `Alluic/Tradingview`.
4. Use branch `main`.
5. Use main file path `app.py`.
6. Deploy.

The dashboard builds its own public-data breadth signals on startup if the local database is empty. The hosted Streamlit app is for viewing research; scheduled email alerts should run through GitHub Actions.

## Scheduled Email Alerts

GitHub Actions workflow:

```text
.github/workflows/zscore-alert.yml
```

It runs weekdays at `22:15 UTC`, which is `6:15 PM Eastern` during daylight saving time. During standard time, change the cron line to `15 23 * * 1-5` if you want the run to remain near 6:15 PM Eastern.

Add these repository secrets in GitHub:

```text
TV_ALERT_SMTP_HOST
TV_ALERT_SMTP_PORT
TV_ALERT_SMTP_USERNAME
TV_ALERT_SMTP_PASSWORD
TV_ALERT_EMAIL_FROM
TV_ALERT_EMAIL_TO
TV_ALERT_SMTP_USE_TLS
```

For Gmail, use an app password, not your normal Google account password.

## Local Push

This machine currently does not have `git` or `gh` available on PATH. After installing Git for Windows, push with:

```powershell
cd "C:\Users\ciull\Desktop\Coding Projects\Trading View"
git init
git branch -M main
git remote add origin https://github.com/Alluic/Tradingview.git
git add .
git commit -m "Initial TradingView signal dashboard"
git push -u origin main
```
