# remote-agents

Remote control for [pi.dev](https://pi.dev) coding agent sessions from any browser.

## Architecture

- **Backend**: FastAPI + asyncio subprocess management
- **Frontend**: Svelte 5 SPA
- **Network**: Tailscale only (no public ports)

## Development

### Backend

```bash
cd backend
uv sync
uv run pytest          # run tests
uv run uvicorn app.main:app --reload  # start dev server
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev               # start dev server
pnpm build             # production build
```

## Documentation

See [docs/](docs/) for:
- [00-patterns.md](docs/00-patterns.md) — Landscape overview
- [01-usecases.md](docs/01-usecases.md) — Use case specifications
- [02-architecture.md](docs/02-architecture.md) — Architecture decisions
- [03-build-plan.md](docs/03-build-plan.md) — Milestone plan
