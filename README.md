# remote-agents

Remote control for [pi.dev](https://pi.dev) coding agent sessions from any browser, including iPhone.

## Overview

**remote-agents** lets you start, resume, and steer long-running `pi.dev` coding agent sessions on a remote VPS from any device with a browser. The system exposes a minimal Web Interface backed by `pi.dev`'s RPC protocol over WebSocket.

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Browser / PWA  │ ──WS──▶ │  FastAPI Backend │ ──RPC──▶ │  pi --mode rpc  │
│  (Svelte 5)     │ ◀─WS──  │  (Python 3.13)  │ ◀─RPC──  │  (Node.js)      │
└─────────────────┘         └─────────────────┘         └─────────────────┘
                                   │
                                   ▼
                            ~/.pi/agent/sessions/*.jsonl
                            (persistent session storage)
```

## Features

- **Start** new agent sessions against any repository in your workspace
- **Resume** live or cold (stopped) sessions from any device
- **Steer** running agents with follow-up messages
- **Survey** all sessions (live and cold) in one view
- **Mobile-first** UI that works on iPhone Safari
- **Tailscale-only** access — no public internet exposure

## Quick Start

### Prerequisites

- **Python 3.13+** — [uv](https://docs.astral.sh/uv/) package manager
- **Node.js 22+** — for pi.dev
- **pi.dev** — `npm install -g @mariozechner/pi-coding-agent`
- **pnpm** — `npm install -g pnpm`

### 1. Clone the repository

```bash
git clone https://github.com/m1981/remote-agents.git
cd remote-agents
```

### 2. Setup backend

```bash
cd backend
uv sync                    # Install dependencies
uv run pytest              # Run tests (123 tests)
```

### 3. Setup frontend

```bash
cd ../frontend
pnpm install               # Install dependencies
pnpm run build             # Build for production
```

### 4. Run locally

**Terminal 1 — Backend:**
```bash
cd backend
export PI_WORKSPACE=/path/to/your/projects  # Directory containing your repos
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

**Terminal 2 — Frontend (development):**
```bash
cd frontend
pnpm run dev               # Starts on http://localhost:5173
```

**Or serve everything from backend (production):**
```bash
# Copy frontend build to backend static files
cp -r frontend/dist/* backend/static/

# Run backend (serves API + static files)
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080
```

### 5. Open in browser

Navigate to `http://localhost:8080` (or `http://localhost:5173` for dev mode).

## Usage

### Start a new session

1. Click **"+ New Session"**
2. Select a repository from the dropdown
3. Optionally enter a session name
4. Click **"Start Session"**
5. You'll be redirected to the session view

### Resume a session

- **Live sessions** (green dot): Click the session name to reattach
- **Cold sessions** (gray dot): Click **"Resume"** to rehydrate the agent

### Interact with the agent

- Type a message and press **Enter** or click **Send**
- While the agent is streaming, your messages are sent as **steering** commands
- Click **Abort** to stop the current agent operation

### Session view

- **Connection status**: Shows connected/connecting/disconnected
- **Streaming indicator**: Pulses when the agent is generating
- **Message bubbles**: User messages (blue), agent messages (white)
- **Thinking blocks**: Collapsed by default, click to expand
- **Tool calls**: Shows tool name and arguments

## Deployment (VPS)

### Prerequisites

- **Hetzner CX22** (or similar) — Ubuntu 24.04, 2 vCPU, 4 GB RAM (~€4.50/mo)
- **Tailscale** account and network

### 1. Provision the VPS

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Create a non-root user
adduser deploy
usermod -aG sudo deploy
su - deploy
```

### 2. Install dependencies

```bash
# System packages
sudo apt update && sudo apt install -y git curl

# Install Node.js (for pi)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Install pi
npm install -g @mariozechner/pi-coding-agent

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Install pnpm
npm install -g pnpm
```

### 3. Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Follow the auth link to join your tailnet

# Get your tailnet IP
tailscale ip -4
# Output: 100.x.x.x
```

### 4. Clone and setup

```bash
cd /srv
git clone https://github.com/m1981/remote-agents.git
cd remote-agents

# Backend
cd backend
uv sync

# Frontend
cd ../frontend
pnpm install
pnpm run build

# Copy frontend to backend static
mkdir -p ../backend/static
cp -r dist/* ../backend/static/
```

### 5. Create workspace

```bash
# Create workspace directory for your repos
sudo mkdir -p /srv/workspace
sudo chown deploy:deploy /srv/workspace

# Clone your repos
cd /srv/workspace
git clone https://github.com/you/project-a.git
git clone https://github.com/you/project-b.git
```

### 6. Configure systemd service

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/remote-agents.service << 'EOF'
[Unit]
Description=remote-agents Backend
After=network-online.target tailscaled.service

[Service]
Type=simple
WorkingDirectory=/srv/remote-agents/backend
ExecStart=/srv/remote-agents/backend/.venv/bin/uvicorn app.main:app \
  --host 100.x.x.x \
  --port 8080
Environment=PI_WORKSPACE=/srv/workspace
Environment=PATH=/home/deploy/.local/bin:/usr/local/bin:/usr/bin:/bin
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# IMPORTANT: Replace 100.x.x.x with your actual tailnet IP from step 3

# Enable and start
systemctl --user daemon-reload
systemctl --user enable remote-agents
systemctl --user start remote-agents

# Check status
systemctl --user status remote-agents
```

### 7. Enable lingering (survive logout)

```bash
sudo loginctl enable-linger deploy
```

### 8. Verify Tailscale-only access

```bash
# From your VPS, try to access from public IP (should fail)
curl http://your-public-ip:8080/health
# Expected: Connection refused

# From your laptop (on tailnet), access the app
curl http://100.x.x.x:8080/health
# Expected: {"status":"ok"}
```

### 9. Access from iPhone

1. Install Tailscale on your iPhone from the App Store
2. Connect to your tailnet
3. Open Safari and navigate to `http://100.x.x.x:8080`
4. Tap **Share → Add to Home Screen** for PWA experience

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PI_WORKSPACE` | `/tmp/workspace` | Root directory containing repositories |
| `PI_HOST` | `127.0.0.1` | Bind address (use tailnet IP in production) |
| `PI_PORT` | `8080` | Port to listen on |

### pi.dev Configuration

pi.dev uses its own configuration at `~/.pi/agent/settings.json`. To change the model or provider:

```bash
# Edit pi settings
nano ~/.pi/agent/settings.json
```

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/repos` | List repositories in workspace |
| `GET` | `/sessions` | List live and cold sessions |
| `POST` | `/sessions` | Spawn new session (`{repo, name?}`) |
| `POST` | `/sessions/{id}/terminate` | Terminate a live session |

### WebSocket

Connect to `ws://host:8080/ws/sessions/{id}`

**Client → Server:**
```json
{"type": "prompt", "message": "Hello!"}
{"type": "steer", "message": "Do this instead"}
{"type": "follow_up", "message": "Also check this"}
{"type": "abort"}
```

**Server → Client:**
```json
{"kind": "snapshot", "state": {...}, "messages": [...]}
{"kind": "event", "event": {...}}
{"kind": "error", "reason": "..."}
```

## Development

### Project Structure

```
remote-agents/
├── backend/
│   ├── app/
│   │   ├── api/           # REST + WebSocket endpoints
│   │   ├── rpc/           # Agent process, framing, types
│   │   └── sessions/      # Registry, cold scanner, sidecar
│   └── tests/             # 123 tests (unit + integration)
├── frontend/
│   └── src/
│       ├── lib/
│       │   ├── components/   # Svelte 5 components
│       │   ├── repositories/ # API + WebSocket clients
│       │   ├── stores/       # Rune-based state management
│       │   └── types/        # TypeScript interfaces
│       └── App.svelte        # SPA router
└── docs/                    # Specifications
```

### Running Tests

```bash
# Backend tests
cd backend
uv run pytest -v

# Frontend build check
cd frontend
pnpm run build
```

### Test Coverage

| Suite | Tests | Description |
|-------|-------|-------------|
| Unit | 47 | Config, framing, types, sidecar, cold scanner |
| Integration | 76 | Agent process, registry, API, WebSocket, edge cases |
| **Total** | **123** | |

## Architecture Decisions

See [docs/](docs/) for detailed specifications:

- [00-patterns.md](docs/00-patterns.md) — Landscape overview of remote agent patterns
- [01-usecases.md](docs/01-usecases.md) — Full use case specifications (UC-1 through UC-5)
- [02-architecture.md](docs/02-architecture.md) — Architecture decisions and component design
- [03-build-plan.md](docs/03-build-plan.md) — Milestone-based build plan

## License

MIT
