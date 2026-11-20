# Deploy Studywise on Render

The repository includes a root-level [`render.yaml`](../../render.yaml) Blueprint. It provisions a free Docker web service and a PostgreSQL database, with the web service rooted at `studywise/`.

1. Sign in to Render and choose **New → Blueprint**.
2. Connect `sagnik3788/AL-assignment` and select the `main` branch.
3. During Blueprint setup, enter your OpenRouter key when prompted for `OPENROUTER_API_KEY`. Keep it in Render's secret environment settings, not in GitHub.
4. Deploy. Render connects the database, runs migrations, and starts the app.
5. Open the deployed URL. No app access key is required; the `OPENROUTER_API_KEY` remains a server-side secret.

Both services are configured for the free tier. Render free web services sleep after 15 minutes without traffic, and free Postgres databases expire after 30 days. The first request after sleep may take about a minute. This is suitable for a short assessment demo, not long-term production storage. See [Render's free instance limitations](https://render.com/docs/free).

The app expects `DATABASE_URL` in SQLAlchemy's `postgresql+psycopg://` form. Render supplies `postgresql://`; the application and Alembic configuration normalize that URL to the installed Psycopg 3 driver.

OpenRouter returned HTTP 402 during the last evaluation retry. Check that the OpenRouter account has available credits before expecting live AI responses. With no valid provider calls, the app returns its safe recovery response; it does not expose the provider key to the browser.
