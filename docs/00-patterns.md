# Running an agent remotely with a local interface — 2026 landscape

For a small personal project, you don't need a heavyweight platform. The space has consolidated into **4 practical patterns**. Pick one based on how much infra you want to own.

## Pattern 1 — Vendor-hosted agent + local CLI bridge (lowest effort)

The agent runs in the vendor's sandbox; you keep a local CLI/IDE that can pull the session down.

- **Claude Code on the web** with `--remote` / `--teleport` — start a session in Anthropic's cloud sandbox, then `claude --teleport <session>` from your laptop to continue locally against your real working tree. Config for setup scripts, network, Docker is in the dashboard. ([docs](https://code.claude.com/docs/en/claude-code-on-the-web))
- **OpenAI Codex Cloud**, **Cursor Background Agents**, **Devin**, **Jules (Google)** — same pattern: cloud worker on an ephemeral VM tied to a GitHub repo, you review/intervene from a web UI or IDE.

✅ Zero ops, free tier usually enough for a personal project.
❌ Your code and API key live on their infra; limited control over the sandbox image; vendor lock-in.

## Pattern 2 — Your own VPS + tmux/mosh + local terminal (the "boring" winner)

This is what most people doing serious personal work landed on in 2026. ~€5/mo Hetzner box, one weekend of setup, then it just works.

```
laptop ──(mosh+ssh)──► VPS ──► tmux ──► claude / opencode / aider
                                  │
                                  └─► your repo (git, neovim, lazygit, yazi)
```

Key pieces:
- **Transport**: `mosh` over `ssh` (survives sleep/network changes, low-latency typing). Tailscale on top if you want zero-config from phone/other devices.
- **Persistence**: `tmux` or `zellij` so the agent keeps running when you disconnect.
- **Local file editing**: either edit in-terminal (nvim) or mount the remote tree with `sshfs` / VS Code Remote-SSH / JetBrains Gateway. VS Code Remote-SSH is the path of least resistance — local UI, remote filesystem and processes.
- **Agent**: Claude Code, OpenCode, Codex CLI, Aider — all run identically on a Linux VPS.

Good walkthroughs: ["Why and how to run Claude Code on a VPS"](https://medium.com/@lexy_eyn/why-and-how-to-run-claude-code-on-a-vps-657daf79e3ea), [claudefa.st VPS guide](https://claudefa.st/blog/guide/development/infraops-vps-guide), and [herdr](https://coles.codes/posts/herding-agents-with-herdr/) for parallel sessions.

✅ Full control, cheap, agent keeps running 24/7, works from any device.
❌ You own the box (updates, backups, secrets). Need to think about sandboxing if you use `--dangerously-skip-permissions`.

## Pattern 3 — Sandboxed agent boxes (Pattern 2 + isolation)

Same idea as Pattern 2 but each task gets its own ephemeral container/VM. Useful once you start running multiple agents in parallel or letting them run unattended.

- **agentbox** — runs agents in Docker locally or on Hetzner/Daytona/Vercel/E2B, sub-1s checkpoint starts. Works with Claude Code, Codex, OpenCode.
- **agent-deck** — TUI session manager; shares host auth into containers so you don't reauth.
- **Codeman** — tmux+WebUI for managing many Claude/OpenCode sessions, with a Mosh-style local-echo layer for remote latency.
- **E2B / Daytona / Modal sandboxes** — if you'd rather rent the sandbox per-run than keep a VPS up.

✅ Safe to give the agent broad permissions; easy parallelism.
❌ More moving parts than you probably need for one personal project.

## Pattern 4 — Phone/web remote control of your local machine

Inverse of Pattern 2: agent runs on your beefy desktop at home, you poke it from anywhere.

- **Claude Code Remote Control** (built-in, 2026) — outbound TLS to Anthropic's relay, no inbound ports. ([guide](https://claudefa.st/blog/guide/development/remote-control-guide))
- **Moshi** ([getmoshi.app](https://getmoshi.app/)) — SSH/Mosh terminal app tuned for Claude Code/Codex, good iOS/macOS story.
- **Tailscale + Termux/Blink + tmux** — the DIY version.

✅ Uses hardware you already own. No monthly bill.
❌ Desktop must stay on; home network/ISP becomes your SLA.

---

## Recommendation for a small personal project

Start with **Pattern 2**:

1. €4.50/mo Hetzner CX22 (Ubuntu 24.04, 2 vCPU, 4 GB).
2. Install: `mosh`, `tmux`, `git`, `gh`, Node (for Claude Code / OpenCode), `nvim` or just use VS Code Remote-SSH.
3. Tailscale for painless access from laptop + phone.
4. Pick one agent — **Claude Code** if you want polish, **OpenCode** if you want open-source and provider flexibility ([opencode.ai](https://opencode.ai)).
5. Workflow: `mosh vps -- tmux a -t work` for the agent, VS Code Remote-SSH window open for diffs/file browsing.

If/when you need to run several tasks at once or let the agent run unattended, layer **agentbox** or **agent-deck** on top — they slot into the same VPS without rearchitecting anything.

## Curated lists to track

- [bradAGI/awesome-cli-coding-agents](https://github.com/bradAGI/awesome-cli-coding-agents)
- [andyrewlee/awesome-agent-orchestrators](https://github.com/andyrewlee/awesome-agent-orchestrators)
