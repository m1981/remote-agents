# remote-agents — Use Case Specification

## 1. Domain Understanding and Glossary

### Context

`remote-agents` is a single-user system that lets the Owner start and resume long-running `pi.dev` coding agent sessions on a remote VPS from any device with a browser, including an iPhone. The system exposes a minimal web interface backed by a terminal multiplexer; it does not provide file editing, diffing, or PR review — those remain the agent's responsibility inside the session.

### Core Value Proposition

Enable the Owner to drive a `pi.dev` coding agent against multiple repositories from any browser, without keeping a local terminal connected, and without exposing anything to the public internet.

### Domain Glossary

| Term | Definition |
|------|------------|
| Owner | The sole human user of the system. |
| Host | The remote VPS running the system. |
| Workspace | The root directory on the Host containing all repositories the agent may operate on. |
| Repository | A Git working tree located directly under the Workspace. |
| Agent | A `pi.dev` (pi-coding-agent) process running inside a multiplexer pane. |
| Session | A named, persistent multiplexer window hosting exactly one Agent, bound to a Repository at creation time. |
| Web Interface | The HTTP UI served on the Host's tailnet address, listing Sessions and exposing each Session's terminal. |
| Tailnet | The private Tailscale network through which the Owner reaches the Host. |
| Multiplexer | The terminal multiplexer (e.g. `tmux`) that owns Session lifecycle on the Host. |

## 2. Business Rules and Constraints

- **BR-1 (Tailnet-Only Access):** The Web Interface is reachable exclusively from inside the Owner's Tailnet. No port is published to the public internet.
- **BR-2 (Single Owner):** The system assumes one identity. Authentication is delegated to Tailscale; no in-app user model exists.
- **BR-3 (Session-Per-Window):** Each Session corresponds to exactly one Multiplexer window. Window name equals Session name and must be unique among live Sessions.
- **BR-4 (Repository Binding):** A Session is bound to a single Repository at creation. The Agent may read or write other Repositories in the Workspace during execution; the binding only defines the initial working directory.
- **BR-5 (Volatile Sessions):** Sessions are not required to survive Host reboot. After reboot the Session list is empty.
- **BR-6 (No File Surface):** The Web Interface exposes terminal I/O only. It does not render, upload, download, or edit files.
- **BR-7 (Mobile Parity):** Every Owner goal must be achievable from iPhone Safari with no desktop-only interaction.

## 3. Scope Definition

| Topic | In | Out |
|-------|----|-----|
| Start a new Agent Session bound to a Repository | X | |
| List live Sessions | X | |
| Resume (attach to) a live Session from any browser | X | |
| Send keystrokes to the Agent from the browser | X | |
| Terminate a Session | X | |
| Multiple Repositories in one Workspace | X | |
| iPhone Safari support | X | |
| Tailscale-based access control | X | |
| File editor / diff viewer / file browser | | X |
| PR creation or review UI | | X |
| Multi-agent orchestration / parallel agent coordination | | X |
| Session persistence across Host reboot | | X |
| Public internet exposure / TLS for non-tailnet clients | | X |
| Usage metrics, billing, notifications | | X |
| User management, sharing, RBAC | | X |
| Backup of agent state or repository contents | | X |

## 4. Actor-Goal List

| Actor | User-Level Goal |
|-------|----------------|
| Owner | Start an Agent Session against a chosen Repository. |
| Owner | Resume an existing Agent Session from a browser. |
| Owner | Terminate an Agent Session. |
| Owner | Survey what Sessions are currently live. |

## 5. Fully Dressed Use Cases

---

**Use Case 1: Start Agent Session**

- **Primary Actor:** Owner
- **Scope:** remote-agents (Host + Web Interface)
- **Level:** User-Goal
- **Stakeholders and Interests:**
  - Owner: wants a fresh Agent ready to receive instructions against a chosen Repository.
  - Host: wants exactly one Multiplexer window per Session and no orphaned processes.
- **Preconditions:**
  - Owner is connected to the Tailnet.
  - The Workspace contains at least one Repository.
  - The Multiplexer is running on the Host.
- **Minimal Guarantees:**
  - If start fails, no half-created Session appears in the Session list.
- **Success Guarantees:**
  - A new Session exists, bound to the chosen Repository, with the Agent running and awaiting input.
  - The new Session is visible in the Session list.
- **Trigger:** Owner requests a new Session from the Web Interface.

**Main Success Scenario (MSS):**
1. Owner selects a Repository from the Workspace.
2. Owner names the new Session.
3. System validates the name against live Session names per BR-3.
4. System creates a Multiplexer window in the Workspace, sets its working directory to the Repository, and launches the Agent inside it.
5. System adds the Session to the Session list and presents its terminal view to the Owner.
6. Owner confirms the Agent is ready and begins issuing instructions.

**Extensions:**
- 3a. System detects the chosen name collides with a live Session:
  - 3a1. System rejects the request and reports the conflict.
  - 3a2. Use case returns to step 2.
- 1a. System detects the Workspace contains no Repository:
  - 1a1. System reports the empty Workspace.
  - 1a2. Use case ends in failure.
- 4a. System detects the Agent process exits before becoming ready:
  - 4a1. System closes the Multiplexer window.
  - 4a2. System reports the failure to the Owner.
  - 4a3. Use case ends in failure.

**Technology and Data Variations:**
- 1: Repository selection may be presented as a list of immediate subdirectories of the Workspace.
- 4: The Multiplexer may be `tmux`, `zellij`, or equivalent without changing behavior.

---

**Use Case 2: Resume Agent Session**

- **Primary Actor:** Owner
- **Scope:** remote-agents (Host + Web Interface)
- **Level:** User-Goal
- **Stakeholders and Interests:**
  - Owner: wants to pick up an ongoing Agent interaction from a different device.
  - Host: wants concurrent viewers of the same Session to see consistent terminal state.
- **Preconditions:**
  - Owner is connected to the Tailnet.
  - At least one live Session exists.
- **Minimal Guarantees:**
  - Resuming a Session never alters Agent state on its own.
- **Success Guarantees:**
  - Owner sees the current terminal output of the chosen Session and can send input to its Agent.
- **Trigger:** Owner opens the Web Interface and selects a live Session.

**Main Success Scenario (MSS):**
1. Owner opens the Web Interface.
2. System presents the list of live Sessions per BR-3.
3. Owner selects a Session.
4. System attaches the browser view to the Session's Multiplexer window and renders current terminal state.
5. Owner inspects Agent output and resumes interaction.

**Extensions:**
- 2a. System detects no live Sessions exist:
  - 2a1. System presents an empty list and offers Start Agent Session (UC-1).
  - 2a2. Use case ends in success with no Session attached.
- 3a. System detects the selected Session ended between listing and selection:
  - 3a1. System reports the Session no longer exists.
  - 3a2. Use case returns to step 2.

**Technology and Data Variations:**
- 4: Terminal rendering may use any browser-compatible terminal emulator (e.g. xterm.js) without changing behavior.

---

**Use Case 3: Terminate Agent Session**

- **Primary Actor:** Owner
- **Scope:** remote-agents (Host + Web Interface)
- **Level:** User-Goal
- **Stakeholders and Interests:**
  - Owner: wants to free a Session name and stop a no-longer-needed Agent.
  - Host: wants the Agent process and its Multiplexer window removed together.
- **Preconditions:**
  - Owner is connected to the Tailnet.
  - The target Session is live.
- **Minimal Guarantees:**
  - If termination fails partway, the Session either remains fully live or is fully removed; no zombie window remains in the list.
- **Success Guarantees:**
  - The target Session is absent from the Session list.
  - The Agent process and its Multiplexer window are gone.
- **Trigger:** Owner requests termination of a specific Session.

**Main Success Scenario (MSS):**
1. Owner selects a live Session.
2. Owner requests termination and confirms intent.
3. System signals the Agent to stop and closes the Multiplexer window.
4. System removes the Session from the Session list.
5. System confirms termination to the Owner.

**Extensions:**
- 3a. System detects the Agent does not exit within the termination timeout:
  - 3a1. System force-kills the Multiplexer window.
  - 3a2. Use case returns to step 4.
- 1a. System detects the Session ended before the request was issued:
  - 1a1. System reports the Session is already gone.
  - 1a2. Use case ends in success.

**Technology and Data Variations:**
- 3: Termination signal may be `SIGTERM` followed by `SIGKILL`, or a multiplexer-native `kill-window`, without changing behavior.

---

**Use Case 4: Survey Live Sessions**

- **Primary Actor:** Owner
- **Scope:** remote-agents (Host + Web Interface)
- **Level:** User-Goal
- **Stakeholders and Interests:**
  - Owner: wants an at-a-glance view of which Agents are running and against which Repository.
- **Preconditions:**
  - Owner is connected to the Tailnet.
- **Minimal Guarantees:**
  - The list reflects Multiplexer reality at request time; no cached or stale Sessions are shown.
- **Success Guarantees:**
  - Owner sees the set of live Sessions with Session name and bound Repository.
- **Trigger:** Owner opens the Web Interface root.

**Main Success Scenario (MSS):**
1. Owner opens the Web Interface root.
2. System queries the Multiplexer for live windows in the Workspace.
3. System renders each live Session with its name and bound Repository.
4. Owner reads the list and chooses to start (UC-1), resume (UC-2), or terminate (UC-3) a Session.

**Extensions:**
- 2a. System detects the Multiplexer is unreachable:
  - 2a1. System reports the Host is not ready.
  - 2a2. Use case ends in failure.

**Technology and Data Variations:**
- 3: The list may be rendered as a table, cards, or plain list without changing behavior.
