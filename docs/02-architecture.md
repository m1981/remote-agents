# remote-agents — Architecture

Companion to [00-patterns.md](00-patterns.md) and [01-usecases.md](01-usecases.md).
This document is the **spoke** for HOW; the use cases remain the behavioural contract.

## 1. Chosen shape (one-line summary)

A small FastAPI Backend on a Tailscale-only VPS that owns one `pi --mode rpc` subprocess per Live Session and proxies its JSONL events to browsers over WebSocket. No tmux, no file editor, no public exposure.

## 2. Component diagram

```
┌────────────────────────────┐
│ iPhone Safari / Desktop    │
│ (browser, Svelte SPA)      │
└──────────────┬─────────────┘
               │ HTTPS + WebSocket
               │ (tailnet only, BR-1)
┌──────────────▼─────────────────────────────────────────────┐
│                       Host (VPS)                           │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Backend  —  FastAPI + uvicorn                       │  │
│  │                                                      │  │
│  │   REST:      /repos, /sessions (live + cold)         │  │
│  │   WebSocket: /ws/sessions/{id}                       │  │
│  │                                                      │  │
│  │   SessionRegistry  (in-memory)                       │  │
│  │     session_id → AgentProcess                        │  │
│  │                                                      │  │
│  │   AgentProcess                                       │  │
│  │     ├─ asyncio.subprocess (`pi --mode rpc ...`)      │  │
│  │     ├─ stdin  writer  ◀── commands from WS           │  │
│  │     ├─ stdout reader  ──▶ fan-out to WS subscribers  │  │
│  │     └─ ring buffer of last N events (for re-attach)  │  │
│  └─────────────┬──────────────────────────┬─────────────┘  │
│                │ stdio (JSONL)            │ filesystem     │
│  ┌─────────────▼─────────┐  ┌─────────────▼─────────────┐  │
│  │ pi --mode rpc         │  │ ~/.pi/agent/sessions/     │  │
│  │  (one per Live        │  │   <workspace>/*.jsonl     │  │
│  │   Session, cwd =      │  │  (durable, BR-5)          │  │
│  │   chosen Repository)  │  └───────────────────────────┘  │
│  └───────────────────────┘                                 │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ /srv/workspace/                                      │  │
│  │   ├─ project1/   (Repository)                        │  │
│  │   ├─ project2/   (Repository)                        │  │
│  │   └─ utils/      (Repository)                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  tailscaled (only listener exposed beyond loopback)        │
└────────────────────────────────────────────────────────────┘
```

## 3. Process model

| Process | Lifetime | Count | Owner |
|---|---|---|---|
| `tailscaled` | system | 1 | systemd |
| Backend (`uvicorn`) | system | 1 | systemd-user unit |
| Agent (`pi --mode rpc`) | per Live Session | 0..N | Backend, spawned via `asyncio.create_subprocess_exec` |

Backend restarts ⇒ all Live Sessions become Cold (BR-5). On restart, Backend rebuilds the Cold list by scanning the session directory; it does not auto-resurrect Agents.

## 4. RPC plumbing — the only non-trivial part

Each `AgentProcess` is a small state machine wrapping the subprocess and its stdio.

```
        ┌──────────────────────────────────────────────┐
        │              AgentProcess                    │
        │                                              │
WS in ──▶│  command_queue  ──▶  stdin_writer ──▶ pi    │
        │                                              │
        │  stdout_reader  ◀── pi                       │
        │       │                                      │
        │       ├─▶ correlate `response` by id         │
        │       │      (resolve pending futures)       │
        │       │                                      │
        │       └─▶ broadcast `event` to subscribers   │
        │             also append to ring buffer       │
        │                                              │
WS out ◀│  subscriber set  (one per attached browser)  │
        └──────────────────────────────────────────────┘
```

Key rules:

- **JSONL framing.** Split stdout on `\n` only. Strip optional trailing `\r`. Do **not** use `asyncio.StreamReader.readline()` blindly — it's `\n`-based and fine, but never use anything that splits on Unicode line separators (RPC doc warns about this). Document the choice in code.
- **Request correlation.** Every outbound command gets an incrementing `id`. Backend keeps a `dict[id, Future]` and resolves on matching `response` (BR-8).
- **Ring buffer.** Keep last ~200 events per Live Session so a re-attaching browser (UC-2) can replay enough to render a coherent view without calling `get_messages` for every reconnect. `get_messages` is still used on first attach.
- **Backpressure.** `stdout_reader` must drain the pipe even if no browser is attached, otherwise `pi` will block on writes. Ring buffer absorbs idle periods.
- **One Agent per Session ID (BR-3).** Enforced by `SessionRegistry.spawn()` taking a lock keyed on session_id.

## 5. HTTP / WebSocket surface

Minimal, REST-ish. All routes require the tailnet (BR-1) — enforce via uvicorn `--host` bound to the tailnet IP plus a middleware check on `X-Forwarded-For` / peer IP if you put Caddy in front.

| Method | Path | Purpose | Use case |
|---|---|---|---|
| GET | `/repos` | List immediate subdirs of Workspace | UC-1 |
| GET | `/sessions` | `{live: [...], cold: [...]}` | UC-5 |
| POST | `/sessions` | Body `{repo, name?}` — spawn new Agent | UC-1 |
| POST | `/sessions/{id}/resume` | Spawn Agent for a Cold Session | UC-3 |
| POST | `/sessions/{id}/terminate` | Abort + signal | UC-4 (terminate) |
| WS | `/ws/sessions/{id}` | Bidirectional: commands ⇄ events | UC-2, UC-4 (steer) |

### WebSocket message shapes

Client → server:

```json
{"type": "prompt",       "message": "..."}
{"type": "steer",        "message": "..."}
{"type": "follow_up",    "message": "..."}
{"type": "abort"}
```

Server → client:

```json
{"kind": "snapshot", "state": {...}, "messages": [...]}   // on connect
{"kind": "event",    "event": { /* raw pi RPC event */ }} // streamed
{"kind": "error",    "reason": "..."}
```

The server intentionally forwards `pi`'s raw events under `event` — the frontend already needs to understand them, and a translation layer would just be churn.

## 6. State and persistence

| State | Where | Survives reboot |
|---|---|---|
| Conversation history, tree, labels | `~/.pi/agent/sessions/<ws>/*.jsonl` (owned by pi) | ✅ |
| Session ID → Repository mapping | Sidecar `~/.pi/agent/sessions/<ws>/<id>.repo` (single line) | ✅ |
| Session Name | Inside the JSONL via `set_session_name` | ✅ |
| Live registry (id → process) | Backend memory | ❌ (BR-5) |
| Ring buffer of recent events | Backend memory | ❌ |

The sidecar `.repo` file is the only thing we add to pi's storage. It's needed for UC-3 because pi's session file doesn't record `cwd`.

## 7. Frontend

Constraints: BR-7 (iPhone Safari), BR-6 (no file editor).

- **SPA** in Svelte (matches your `dev-svelte` / `stack-svelte` skills) or any framework you prefer.
- Two views only:
  - **Sessions view** — Live and Cold lists grouped by Repository (UC-5).
  - **Session view** — message log + composer + steer/abort buttons (UC-2, UC-4).
- Renderers needed for pi events: text deltas, thinking deltas (collapsed by default), tool-call cards (`tool_execution_*`), queue badge (`queue_update`), turn separators.
- No diff viewer, no file tree, no editor. Tool results render as plain text or simple cards — that's the BR-6 line.
- PWA manifest so it installs to iPhone home screen and behaves like a chat app.

## 8. Deployment

systemd user unit, mirroring OpenChamber's recipe but simpler:

```ini
# ~/.config/systemd/user/remote-agents.service
[Unit]
Description=remote-agents Backend
After=network-online.target tailscaled.service

[Service]
Type=simple
WorkingDirectory=/srv/remote-agents
ExecStart=/srv/remote-agents/.venv/bin/uvicorn app:app \
  --host 100.x.x.x \
  --port 8080
Environment=PI_WORKSPACE=/srv/workspace
Environment=PATH=/home/user/.nvm/versions/node/v22.14.0/bin:/usr/local/bin:/usr/bin:/bin
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Notes:
- `--host` is the **tailnet IP**, not `0.0.0.0`. Belt-and-braces enforcement of BR-1.
- `PATH` must include the directory containing `pi` (systemd user services don't source your shell profile — same gotcha OpenChamber documents).
- No reverse proxy required inside the tailnet. Add Caddy only if you later want HTTPS even on tailnet hostnames.

## 9. Decided behaviour

- **Concurrent viewers of one Session.** Allowed and synchronised. Each viewer receives an independent state snapshot on connect; all viewers share the same live event stream. Typing on any device queues the message into the same Agent. No "primary device" concept.
- **Secrets.** API keys live in `~/.pi/agent/...` on the Host. The Backend never reads them; only the spawned `pi` subprocess does.
- **Model selection.** Out of scope for the UI. Default model comes from `~/.pi/agent/settings.json`; the Owner edits that file on the Host to change it.

## 9b. Open questions to decide before implementation

1. **Workspace layout.** Single Workspace root (`/srv/workspace`) vs allow Owner to pick from `~/projects` on the Host? Spec assumes single root — simpler. Confirm.
2. **Idle Agent reaping.** Should the Backend auto-terminate Live Sessions with no viewer attached for N hours? Out of MVP; revisit after first real use.

## 10. What we deliberately did NOT do

- No tmux, no terminal emulator in the browser. The RPC channel is structured, so we render structured.
- No SDK in-process integration. Subprocess isolation per BR-8 makes one crashing Agent harmless.
- No multi-user, no RBAC, no audit log. Single Owner per BR-2.
- No fork/clone UI yet. The capability exists in RPC; UI is deferred (scope table).
- No public ingress. Tailscale is the perimeter.

## 11. Build order

1. `AgentProcess` class with RPC framing, request correlation, ring buffer — unit-tested against a fake `pi` that emits canned JSONL.
2. `SessionRegistry` + `/sessions` REST + `/ws/sessions/{id}` — integration-tested with real `pi --mode rpc` against a throwaway repo.
3. Cold enumeration (`/sessions` GET cold list) by scanning `~/.pi/agent/sessions/`.
4. Frontend: Sessions view → Session view → event renderers in that order.
5. systemd unit + Tailscale ACL + iPhone PWA install.
