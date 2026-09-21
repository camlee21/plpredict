# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Deployment

- **Frontend**: Vercel, Root Directory `frontend`. Env vars: `REACT_APP_API_URL` (the Render backend URL), `REACT_APP_GOOGLE_CLIENT_ID`.
- **Backend**: Render Web Service, build command `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`, start command `gunicorn backend.wsgi:application --timeout 120`. Env vars: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `SYNC_TRIGGER_SECRET`.
- **Database**: Neon Postgres, referenced via `DATABASE_URL`. Falls back to local SQLite when that's unset (the default for local dev).

### Keeping fixtures/scores up to date in production

Locally, `backend/fixtures/apps.py` starts a background thread under `manage.py runserver` that periodically runs `sync_fixtures` and `score_gameweeks` - but that's a dev-only convenience and **does not run under gunicorn**. Render Cron Jobs cost money even at the lowest usage, so production instead uses a secured HTTP endpoint plus a free external scheduler:

1. Render web service env var `SYNC_TRIGGER_SECRET` - a random secret, e.g. from `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. A free scheduler (e.g. [cron-job.org](https://cron-job.org)) configured to `POST` to `https://<render-backend>/api/fixtures/sync/trigger/` every 5-10 minutes, with header `X-Sync-Secret: <the same secret>`.
3. That view (`SyncTriggerView` in `backend/fixtures/views.py`) checks the header against `SYNC_TRIGGER_SECRET` (404s on any mismatch) and, if it matches, runs `sync_fixtures` then `score_gameweeks`.
4. The `--timeout 120` on the Gunicorn start command matters here: those two commands run synchronously inside the request, and Gunicorn's *default* 30s worker timeout is easily exceeded on Render's free-tier CPU, silently killing the worker mid-sync and rolling back the whole `@transaction.atomic` sync before anything is saved.

The cron job is the only thing that pulls new fixtures and results, so its interval is the limit on how fresh the app can be. It also keeps the free Render instance awake: Render spins a free service down after 15 minutes without traffic, so keep the schedule under that.

The frontend caches API responses with TanStack Query and re-checks them on a schedule that follows the gameweek calendar. Between gameweeks it re-checks at most every 15 minutes. While a gameweek is live (from its deadline until it's scored), whatever is on screen is polled every minute, only while the tab is visible. All the timings are in `frontend/src/api/freshness.js`. The cache is also saved in the browser (`frontend/src/api/persist.js`), so reloads and new tabs open with the last data while it's re-checked. When you log in or out, everything saved is wiped, and each Vercel deploy starts with an empty cache. Once you're logged in, the main pages' data is fetched in the background (`warmCache`), and links fetch their page's data as soon as you hover over or touch them. If you change the cron interval, keep `LIVE_POLL_INTERVAL` roughly in line with it, because polling much faster than the sync runs gains nothing.

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
