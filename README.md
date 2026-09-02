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