# Deployment Guide

## Overview

This document describes how to deploy remote-agents to an Ubuntu VPS.

## Prerequisites

- Ubuntu 24.04+ VPS (OVH, Hetzner, etc.)
- SSH access to the VPS
- API key for your LLM provider (OpenRouter, Anthropic, OpenAI, etc.)
- Domain name (optional, sslip.io works for testing)

## Quick Start

### 1. SSH into your VPS

```bash
ssh ubuntu@YOUR_VPS_IP
```

### 2. Run the setup script

```bash
# Download and run setup script
curl -sSL https://raw.githubusercontent.com/m1981/remote-agents/main/deploy/setup.sh | bash
```

Or manually:

```bash
git clone https://github.com/m1981/remote-agents.git
cd remote-agents/deploy
chmod +x setup.sh
./setup.sh
```

### 3. Configure API Key

Create the pi auth file with your API key:

```bash
mkdir -p ~/.pi/agent
cat > ~/.pi/agent/auth.json << 'EOF'
{
  "YOUR_PROVIDER": {
    "type": "api_key",
    "key": "YOUR_API_KEY"
  }
}
EOF
chmod 600 ~/.pi/agent/auth.json
```

**Supported providers:**

| Provider | Key Name | Example Model |
|----------|----------|---------------|
| OpenRouter | `openrouter` | `anthropic/claude-sonnet-4` |
| Anthropic | `anthropic` | `claude-sonnet-4` |
| OpenAI | `openai` | `gpt-4` |
| opencode-go | `opencode-go` | `mimo-v2.5-pro` |

### 4. Configure Systemd Service

```bash
mkdir -p ~/.config/systemd/user
cp /home/ubuntu/remote-agents/deploy/remote-agents.service ~/.config/systemd/user/

# Edit if needed (change model, provider, etc.)
nano ~/.config/systemd/user/remote-agents.service

# Enable and start
systemctl --user daemon-reload
systemctl --user enable remote-agents
systemctl --user start remote-agents

# Enable lingering (survives logout)
sudo loginctl enable-linger ubuntu
```

### 5. Configure Caddy (HTTPS)

```bash
# Edit Caddyfile with your domain
sudo nano /etc/caddy/Caddyfile

# Example for sslip.io:
# YOUR_IP.sslip.io {
#     reverse_proxy localhost:8080
# }

# Restart Caddy
sudo systemctl restart caddy
```

### 6. Configure Firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

### 7. Add Repositories

```bash
sudo mkdir -p /srv/workspace
sudo chown ubuntu:ubuntu /srv/workspace

# Clone your repos
cd /srv/workspace
git clone https://github.com/you/project.git
```

### 8. Verify

```bash
# Check service status
systemctl --user status remote-agents

# Check health
curl https://YOUR_DOMAIN/health

# Open in browser
echo "https://YOUR_DOMAIN"
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PI_WORKSPACE` | `/tmp/workspace` | Root directory for repositories |
| `PI_PROVIDER` | (required) | LLM provider name |
| `PI_MODEL` | (required) | Model identifier |

### Systemd Service Location

```
~/.config/systemd/user/remote-agents.service
```

### Caddy Config Location

```
/etc/caddy/Caddyfile
```

### Pi Auth File

```
~/.pi/agent/auth.json
```

## Updating

```bash
cd /home/ubuntu/remote-agents
git pull

# Rebuild frontend if changed
cd frontend
pnpm run build
cp -r dist/* ../backend/static/

# Restart service
systemctl --user restart remote-agents
```

## Troubleshooting

### Service won't start

```bash
# Check logs
journalctl --user -u remote-agents -n 50

# Check pi config
cat ~/.pi/agent/auth.json
pi --version
```

### WebSocket not connecting

- Check Caddy is running: `sudo systemctl status caddy`
- Check firewall allows port 443: `sudo ufw status`
- Check service is running: `systemctl --user status remote-agents`

### No repos showing

```bash
# Check workspace directory
ls -la /srv/workspace/

# Check API
curl https://YOUR_DOMAIN/repos
```

## Security Notes

- API keys are stored in `~/.pi/agent/auth.json` (mode 600)
- Never commit API keys to the repository
- Use Tailscale for additional network security (optional)
- Caddy provides automatic HTTPS via Let's Encrypt

## File Locations

| File | Location | In Repo? |
|------|----------|----------|
| Application code | `/home/ubuntu/remote-agents/` | ✅ Yes |
| Systemd service | `~/.config/systemd/user/remote-agents.service` | ✅ Template |
| Caddy config | `/etc/caddy/Caddyfile` | ✅ Template |
| Pi auth | `~/.pi/agent/auth.json` | ❌ No (secrets) |
| Workspace | `/srv/workspace/` | ❌ No (user data) |
| Session files | `~/.pi/agent/sessions/` | ❌ No (runtime) |
