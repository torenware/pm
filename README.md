# Project Management MVP

## Run

macOS:

```sh
./scripts/start-macos.sh
```

Linux:

```sh
./scripts/start-linux.sh
```

Windows PowerShell:

```powershell
./scripts/start-windows.ps1
```

Open <http://localhost:8000>. Set `APP_PORT` in the root `.env` file to use a different host port.

Sign in with username `user` and password `password`. Sessions expire after eight hours. Set a stable `SESSION_SECRET` in the root `.env` file to keep existing sessions valid across application recreation.

Use the matching `stop-*` script to stop the application. Board data and hashed sessions are stored in `data/pm.db` and retained in the ignored repository-local `data/` directory.

## Test

```sh
cd backend
uv run pytest
```

```sh
cd frontend
npm run lint
npm run test:unit
npm run test:e2e
```

To run Playwright against the Docker application, start it and set `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000` when running `npm run test:e2e`.

## AI connectivity

The authenticated `POST /api/ai/diagnostic` endpoint asks the configured KodeKloud
`gpt-oss-120b` model `2+2`. Start the application, sign in, and call the endpoint
with the returned session cookie. The server reads `KK_BASE_URL` and `KK_API_KEY`
from the root `.env`; these values must never be sent to the browser or logs.