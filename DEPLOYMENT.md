# Deployment

## Dashboard Hosting

Host the dashboard with Streamlit Community Cloud:

1. Push this project to your GitHub repository.
2. Go to `https://share.streamlit.io`.
3. Create a new app from your repository.
4. Use branch `main`.
5. Use main file path `app.py`.
6. Deploy.

The dashboard builds its own public-data breadth signals on startup if the local database is empty. The hosted Streamlit app is for viewing research; scheduled email alerts should run through GitHub Actions.

For local viewing:

```powershell
streamlit run app.py
```

Then open `http://localhost:8501`.

## Scheduled Email Alerts

GitHub Actions workflow:

```text
.github/workflows/zscore-alert.yml
```

It runs weekdays at `13:30 UTC`, which is `9:30 AM Eastern` market open during daylight saving time. During standard time, change the cron line to `30 14 * * 1-5` if you want the run to remain at 9:30 AM Eastern.

Alert rules:

```text
Signals: MMTW, MMFI, MMOH, MMTH
Thresholds: +/-1.0, +/-1.5, +/-2.0
Email behavior: send only when a signal crosses a threshold
```

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

To push this project to a new GitHub repository:

```powershell
git init
git branch -M main
git remote add origin https://github.com/<owner>/<repo>.git
git add .
git commit -m "Initial market breadth signal dashboard"
git push -u origin main
```
