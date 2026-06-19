# remote-agents — Build Plan

Companion to [01-usecases.md](01-usecases.md) and [02-architecture.md](02-architecture.md).
This document breaks step 1 of architecture §11 into concrete, testable tasks. It is the **noob-friendly path** from empty repo to working iPhone-accessible app.

## 0. Guiding rules

- **One commit per task.** Each task is a green test or a working `curl`. No "WIP" commits.
- **Tests before glue.** Every backend task lists its test first, implementation second.
- **No real LLM calls until milestone M3.** Use a fake `pi` binary that emits canned JSONL. Saves money, makes tests deterministic.
- **Run on your Mac first.** Don't touch the VPS until M5. localhost → tailnet is one config line.

## 1. Stack lock-in

| Layer | Choice | Why |
|---|---|---|
| Backend language | Python 3.12+ | Your loaded `dev-python-fast-api` + `stack-fastapi` skills |
| Web framework | FastAPI + uvicorn | Native async, WebSocket support, OpenAPI for free |
| Async subprocess | `asyncio.create_subprocess_exec` | Stdlib; matches RPC stdio model |
| Test framework | `pytest` + `pytest-asyncio` + `httpx` | FastAPI standard |
| Frontend | Svelte 5 + Vite | Your loaded `dev-svelte` / `stack-svelte` skills, small bundle for mobile |
| WS client | Native browser `WebSocket` | No library needed |
| Package manager (Py) | `uv` | Fast, lockfile, single binary |
| Package manager (JS) | `pnpm` | Or npm; doesn't matter for one app |
| Process supervisor | systemd-user | Already on Linux; matches §8 |
| Network perimeter | Tailscale | Already decided (BR-1) |

If you don't know `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`. Treats Python like Node treats npm.

## 2. Repository layout

```
remote-agents/
├── docs/                          # what you already have
├── backend/
│   ├── pyproject.toml             # uv-managed
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app factory
│   │   ├── config.py              # Settings (workspace path, port)
│   │   ├── rpc/
│   │   │   ├── __init__.py
│   │   │   ├── framing.py         # JSONL line splitter
│   │   │   ├── agent_process.py   # the state machine
│   │   │   └── types.py           # Pydantic models for RPC commands/events
│   │   ├── sessions/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py        # SessionRegistry (in-memory)
│   │   │   ├── cold.py            # JSONL directory scanner
│   │   │   └── sidecar.py         # <id>.repo file I/O
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── repos.py           # GET /repos
│   │       ├── sessions.py        # REST endpoints
│   │       └── ws.py              # WebSocket /ws/sessions/{id}
│   └── tests/
│       ├── conftest.py            # fixtures: fake-pi, tmp workspace
│       ├── fake_pi.py             # stub binary script
│       ├── unit/
│       └── integration/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── app.html
│   │   ├── routes/
│   │   │   ├── +page.svelte                  # sessions list (UC-5)
│   │   │   └── sessions/[id]/+page.svelte    # session view (UC-2, UC-4)
│   │   └── lib/
│   │       ├── api.ts             # REST client
│   │       ├── ws.ts              # WebSocket client + reconnect
│   │       └── events/            # one renderer per pi event kind
│   └── static/manifest.webmanifest # PWA
└── deploy/
    ├── remote-agents.service       # systemd-user unit
    └── README.md                   # 10-step deploy checklist
```

## 3. Milestones

Each milestone ends with a demo you can run. If you can't demo it, the milestone isn't done.

### M0 — Skeleton (½ day)

Demo: `uv run uvicorn app.main:app` returns `{"status": "ok"}` at `/health`.

| # | Task | Test |
|---|------|------|
| 0.1 | `uv init backend` + add `fastapi`, `uvicorn`, `pytest`, `pytest-asyncio`, `httpx` | `uv run pytest` runs zero tests, exits 0 |
| 0.2 | `app/main.py` with `/health` endpoint | `tests/unit/test_health.py` hits it via `TestClient` |
| 0.3 | `app/config.py` with `Settings(workspace: Path, host: str, port: int)` reading env vars | `tests/unit/test_config.py` |
| 0.4 | `frontend/` scaffolded with `npm create vite@latest -- --template svelte-ts` | `npm run dev` renders default page |
| 0.5 | Git: `.gitignore`, single commit "scaffold backend + frontend" | — |

### M1 — RPC plumbing with fake pi (1–2 days, the hard part)

Demo: a pytest sends `{"type":"prompt","message":"hi"}` to a fake pi subprocess via `AgentProcess` and gets back the canned `message_update` events.

| # | Task | Test |
|---|------|------|
| 1.1 | `tests/fake_pi.py` — a tiny Python script that reads JSONL on stdin and emits a hard-coded event sequence on stdout. Executable. | Manual: `echo '{"type":"get_state"}' \| ./fake_pi.py` prints valid JSONL |
| 1.2 | `rpc/framing.py` — `read_jsonl_lines(reader)` async generator. Splits on `\n` only, strips trailing `\r`. | `tests/unit/test_framing.py`: feed it bytes with `\n`, `\r\n`, embedded `U+2028`, partial lines. Assert correct splits. |
| 1.3 | `rpc/types.py` — Pydantic models for commands (`PromptCmd`, `SteerCmd`, `AbortCmd`, ...) and a discriminated union for events. | `tests/unit/test_types.py`: round-trip parse known RPC samples copied from pi docs |
| 1.4 | `rpc/agent_process.py` — `AgentProcess.start(cmd, cwd)`, `.send(cmd) -> Future[Response]`, `.subscribe() -> AsyncIterator[Event]`, `.terminate()`. Ring buffer of last 200 events. | `tests/integration/test_agent_process.py` using fake_pi:<br>• send command → await response with matching `id`<br>• subscribe → receive events in order<br>• subscribe late → ring buffer replays<br>• terminate → subprocess exits within timeout |
| 1.5 | Backpressure test: fake_pi emits 10k events fast, no subscriber attached. AgentProcess must not block. | `tests/integration/test_backpressure.py` |

**Why this is the hard part:** if `AgentProcess` is solid, everything else is CRUD. If it's flaky, you'll debug ghost bugs forever. Spend the time here.

### M2 — Session lifecycle, still with fake pi (1 day)

Demo: `curl -X POST /sessions -d '{"repo":"demo"}'` returns a session id; `GET /sessions` lists it; `curl -X POST /sessions/{id}/terminate` removes it.

| # | Task | Test |
|---|------|------|
| 2.1 | `sessions/sidecar.py` — write/read `<id>.repo` file | `tests/unit/test_sidecar.py` |
| 2.2 | `sessions/registry.py` — `SessionRegistry.spawn(repo)`, `.get(id)`, `.terminate(id)`, `.list_live()`. Per-id lock for BR-3. | `tests/integration/test_registry.py` with fake_pi |
| 2.3 | `sessions/cold.py` — scan workspace session dir, parse JSONL headers, return list[ColdSession] | `tests/unit/test_cold.py` with fixture JSONL files |
| 2.4 | `api/repos.py` — `GET /repos` lists Workspace subdirs | `tests/integration/test_repos.py` |
| 2.5 | `api/sessions.py` — `GET /sessions`, `POST /sessions`, `POST /sessions/{id}/resume`, `POST /sessions/{id}/terminate` | `tests/integration/test_sessions_api.py` |

### M3 — WebSocket bridge + real pi (1 day)

Demo: open `wscat -c ws://localhost:8080/ws/sessions/{id}`, send `{"type":"prompt","message":"list files"}`, see real pi events stream back.

| # | Task | Test |
|---|------|------|
| 3.1 | `api/ws.py` — accept WS, send snapshot (`get_state` + `get_messages`), subscribe to AgentProcess events, forward client commands to stdin | `tests/integration/test_ws_with_fake_pi.py` |
| 3.2 | Concurrent viewers test: two WS clients, both see same events, both can send commands | `tests/integration/test_ws_concurrent.py` (locks in §9 decision A) |
| 3.3 | Smoke test against **real** `pi --mode rpc` on your Mac, against a throwaway repo. Manual. | `docs/manual-smoke.md` checklist you tick off |

After M3 you have a working backend. Everything below is frontend + ops.

### M4 — Minimal frontend (2 days)

Demo: open `http://localhost:5173` on your laptop, start a session against a real repo, type a prompt, see pi respond. Then open the same URL on your phone (same WiFi) — both screens stay in sync.

| # | Task | Acceptance |
|---|------|------|
| 4.1 | `lib/api.ts` — typed REST client | Browser console: `await api.listSessions()` works |
| 4.2 | `lib/ws.ts` — WebSocket wrapper with auto-reconnect and event emitter | Pull network cable, plug back in → reconnects |
| 4.3 | `routes/+page.svelte` — Live + Cold lists grouped by repo, "New session" button | Visual: matches UC-5 |
| 4.4 | `routes/sessions/[id]/+page.svelte` — message log + composer + steer/abort buttons | Visual: matches UC-2, UC-4 |
| 4.5 | Event renderers: text delta (streaming), thinking (collapsed), tool-call cards, queue badge, turn separator | Open same session in two tabs → both render identically |
| 4.6 | PWA manifest + iOS meta tags | iPhone Safari "Add to Home Screen" → installs as app |

### M5 — Deploy to VPS (½ day)

Demo: from iPhone Safari on cellular, over Tailscale, open the app and drive a real pi session against a repo cloned on the VPS.

| # | Task | Acceptance |
|---|------|------|
| 5.1 | Provision Hetzner CX22, Ubuntu 24.04 | `ssh user@vps` works |
| 5.2 | Install `tailscale`, join your tailnet, get tailnet IP | `tailscale ip -4` returns `100.x.x.x` |
| 5.3 | Install `node` (for pi), `pi` itself, `uv`, clone repo, `uv sync` | `pi --version` works as the service user |
| 5.4 | Configure: `PI_WORKSPACE=/srv/workspace`, clone 1–2 test repos there | — |
| 5.5 | Build frontend (`pnpm build`), serve from FastAPI as static files | One process, one port |
| 5.6 | Install systemd-user unit from `deploy/remote-agents.service`, `--host` = tailnet IP | `systemctl --user status remote-agents` is green |
| 5.7 | Disable laptop, leave VPN off, try to reach the URL from public internet | Connection refused (BR-1 holds) |
| 5.8 | Enable Tailscale on iPhone, open URL | App loads, sessions work |

### M6 — Polish (open-ended, optional)

Only do these once M5 has been your daily driver for a week:

- Idle Agent reaping (§9b.2)
- Workspace re-selection on missing repo (UC-3 ext 2a)
- Better cold-session metadata (cost, message count)
- Light/dark theme respecting iOS system setting
- `/share` and `/export` UI buttons (wraps existing pi commands)

## 4. Definition of Done (per task)

A task is done when **all** are true:

1. Code compiles / type-checks (`uv run mypy app` or `tsc --noEmit`)
2. Its named test is green (`uv run pytest <path>` or `vitest run <path>`)
3. The whole suite is still green (`uv run pytest` / `pnpm test`)
4. Lint clean (`ruff check` / `eslint`)
5. Committed with a one-line message naming the task number (`M1.4: AgentProcess core`)

## 5. Risk register (things most likely to bite a noob)

| Risk | Mitigation |
|---|---|
| You spend a week perfecting `AgentProcess` and never ship | Hard limit: M1 = 2 days. If not done, simplify (drop ring buffer, use plain replay). |
| WebSocket reconnect logic eats a weekend | Use the dumbest possible policy: on disconnect, wait 1s, reopen, re-fetch snapshot. Don't try to resume mid-stream. |
| You try to add file editor "just a little" | Re-read BR-6 out loud. Put it in M6 if you really want it. |
| Tailscale ACLs are misconfigured and the app is public | M5.7 is the gate. Don't skip it. |
| pi RPC breaks between versions | Pin `pi` version in deploy README; bump deliberately, re-run M3.3 smoke. |
| Subprocess zombies on Backend crash | systemd `KillMode=mixed` + an `atexit` handler in Backend that terminates all live agents. Add to M5.6. |

## 6. What you do *right now*

1. `cd /Users/michal/PycharmProjects/remote-agents`
2. Read this doc end to end once more.
3. Start M0.1. Stop when you hit `/health` returning 200.
4. Commit. Push.

Everything after that is one task at a time, one commit at a time.
