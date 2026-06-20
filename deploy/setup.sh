#!/bin/bash
# remote-agents VPS setup script
# Run this on a fresh Ubuntu 24.04+ VPS as root or with sudo

set -e

echo "=== remote-agents VPS Setup ==="

# 1. Update system
echo "[1/8] Updating system..."
apt update && apt upgrade -y

# 2. Install dependencies
echo "[2/8] Installing dependencies..."
apt install -y git curl caddy

# 3. Install Node.js 22
echo "[3/8] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs

# 4. Install pi.dev
echo "[4/8] Installing pi.dev..."
npm install -g @mariozechner/pi-coding-agent

# 5. Install uv
echo "[5/8] Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# 6. Install pnpm
echo "[6/8] Installing pnpm..."
npm install -g pnpm

# 7. Clone repository
echo "[7/8] Cloning repository..."
cd /home/ubuntu
git clone https://github.com/m1981/remote-agents.git
cd remote-agents/backend
uv sync

# 8. Build frontend
echo "[8/8] Building frontend..."
cd ../frontend
pnpm install
pnpm run build
cp -r dist/* ../backend/static/

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "1. Configure pi API key (see DEPLOY.md)"
echo "2. Copy deploy/remote-agents.service to ~/.config/systemd/user/"
echo "3. Copy deploy/Caddyfile to /etc/caddy/Caddyfile"
echo "4. Enable and start services"
echo ""
echo "See DEPLOY.md for detailed instructions."
