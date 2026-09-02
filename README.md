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

Sign in with username `user` and password `password`. Sessions expire after eight hours and are invalidated when the application restarts unless `SESSION_SECRET` is set in the root `.env` file.

Use the matching `stop-*` script to stop the application. Application data is retained in the ignored repository-local `data/` directory.

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