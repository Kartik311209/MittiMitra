# Hosting the complete MittiMitra portal

`web/` is only a static project preview. The working application is
`hosted_app.py`: Streamlit runs at `/`, and the existing FastAPI backend runs
at `/api` in the same process. Use `Dockerfile.hosted` on a container host that
supports WebSockets and a single public HTTP port. The app reads the host's
`PORT` environment variable and exposes `GET /__health` for health checks.

## Private test deployment

Do not invite real farmers or collect their real details in this mode. Set
these environment variables in the hosting provider's secret/variable UI,
never in Git:

```text
DEMO_MODE=1
OTP_DELIVERY_MODE=screen
DEMO_ACCESS_PASSWORD=<random password of at least 16 characters>
SCHEME_ADMIN_KEY=<different random secret>
```

The Dockerfile sets `PUBLIC_DEPLOYMENT=1`, and startup rejects an incomplete
configuration. An invite password gates both the UI and API, including
Streamlit's WebSocket. After entering the invite password, testers must use
only fake numbers in the `9000000xxx` range; the short-lived OTP appears on
screen. A demo banner warns against entering real names or personal photos.
The demonstration database is disposable if the host has no persistent disk.
The browser's password prompt uses username `demo` and the configured
`DEMO_ACCESS_PASSWORD`.

For a persistent host, mount one volume at `/app/persistent`. That directory
contains the SQLite database, uploads, and mutable model artifacts. The
Docker build bundles a location-only SQLite database from the tracked LGD
workbooks, so an empty volume or ephemeral Free service can restore the
village directory without re-reading the large workbooks at every cold start.

## Real farmer deployment

Turn off `DEMO_MODE`, use `OTP_DELIVERY_MODE=twilio`, and supply
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID`, and a
strong `SCHEME_ADMIN_KEY` as host secrets. Use HTTPS, persistent storage,
backups, monitoring, and a privacy/consent review before opening registration
to real farmers. Screen OTP must never be used for public real accounts.

The Gemini assistant also needs a server-side `GEMINI_API_KEY`; crop-disease
predictions remain unavailable until a validated model is installed. Neither
is silently presented as working when its dependency is missing.
