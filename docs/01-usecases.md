# remote-agents — Use Case Specification

> **Revision note:** This version replaces the original tmux/ttyd shape with `pi --mode rpc` as the integration surface. The user-visible goals are unchanged; mechanics, persistence semantics, and one new use case (UC-5) are added.

## 1. Domain Understanding and Glossary

### Context

`remote-agents` is a single-user system that lets the Owner start, resume, and steer long-running `pi.dev` coding agent sessions on a remote VPS from any device with a browser, including an iPhone. The system exposes a minimal Web Interface backed by `pi.dev`'s RPC protocol; it does not provide file editing, diffing, or PR review — those remain the Agent's responsibility inside the session.

### Core Value Proposition

Enable the Owner to drive a `pi.dev` coding agent against multiple repositories from any browser, without keeping a local terminal connected, and without exposing anything to the public internet.

### Domain Glossary

| Term | Definition |
|------|------------|
| Owner | The sole human user of the system. |
| Host | The remote VPS running the system. |
| Workspace | The root directory on the Host containing all repositories the Agent may operate on. |
| Repository | A Git working tree located directly under the Workspace. |
| Agent | A `pi.dev` process launched with `--mode rpc`, bound to a Repository as its working directory. |
| Session | A persistent `pi.dev` conversation tree stored as a JSONL file under the Host's session directory, identified by Session ID. |
| Live Session | A Session that currently has a running Agent process attached and is producing or able to produce events. |
| Cold Session | A Session that exists on disk but has no running Agent process. |
| Session ID | The `pi.dev`-assigned UUID identifying a Session across runs. |
| Session Name | An optional human-readable label set by the Owner via `set_session_name`. |
| Backend | The Host-side server process that owns Agent subprocesses and exposes them to browsers. |
| Web Interface | The browser-side UI served by the Backend on the Host's tailnet address. |
| Tailnet | The private Tailscale network through which the Owner reaches the Host. |
| RPC Channel | The JSONL stdin/stdout protocol defined by `pi --mode rpc`. |

## 2. Business Rules and Constraints

- **BR-1 (Tailnet-Only Access):** The Web Interface is reachable exclusively from inside the Owner's Tailnet. No port is published to the public internet.
- **BR-2 (Single Owner):** The system assumes one identity. Authentication is delegated to Tailscale; no in-app user model exists.
- **BR-3 (One Agent Per Live Session):** Each Live Session corresponds to exactly one Agent subprocess on the Host. Two Agents must not be attached to the same Session ID concurrently.
- **BR-4 (Repository Binding):** A Session is bound to a single Repository at creation, set as the Agent's working directory. The Agent may read or write other Repositories in the Workspace during execution; the binding only defines the initial working directory and is recorded by Session Name convention or sidecar metadata.
- **BR-5 (Disk-Persistent Sessions, Volatile Processes):** Sessions persist as `pi.dev` JSONL files across Host reboot. Agent processes do not survive reboot; surviving Sessions become Cold Sessions until resumed.
- **BR-6 (No File Surface):** The Web Interface exposes conversation, tool-call, and steering surfaces only. It does not render, upload, download, or edit files outside what the Agent itself displays through tool results.
- **BR-7 (Mobile Parity):** Every Owner goal must be achievable from iPhone Safari with no desktop-only interaction.
- **BR-8 (RPC As Integration Surface):** The Backend interacts with each Agent only through the `pi --mode rpc` protocol. The Backend does not parse Agent terminal output, does not patch session files directly, and does not invoke `pi.dev` internals.

## 3. Scope Definition

| Topic | In | Out |
|-------|----|-----|
| Start a new Agent Session bound to a Repository | X | |
| Resume a Live Session from any browser | X | |
| Resume a Cold Session (rehydrate Agent from disk) | X | |
| Send prompts and steering messages to the Agent | X | |
| Render streamed Agent events (text, thinking, tool calls) | X | |
| Terminate a Live Session | X | |
| Survey Live and Cold Sessions | X | |
| Multiple Repositories in one Workspace | X | |
| iPhone Safari support | X | |
| Tailscale-based access control | X | |
| Session persistence across Host reboot (via pi.dev JSONL files) | X | |
| File editor / diff viewer / file browser | | X |
| PR creation or review UI | | X |
| Multi-agent orchestration / parallel agent coordination | | X |
| Public internet exposure / TLS for non-tailnet clients | | X |
| Usage metrics, billing, notifications | | X |
| User management, sharing, RBAC | | X |
| Backup of Repository contents or session files | | X |
| Branching / forking sessions from the UI (deferred) | | X |
| Model or thinking-level switching from the UI (deferred) | | X |

## 4. Actor-Goal List

| Actor | User-Level Goal |
|-------|----------------|
| Owner | Start an Agent Session against a chosen Repository. |
| Owner | Resume a Live Session from a browser. |
| Owner | Resume a Cold Session by rehydrating an Agent for it. |
| Owner | Steer or terminate a Live Session. |
| Owner | Survey what Sessions exist, Live and Cold. |

## 5. Fully Dressed Use Cases

---

**Use Case 1: Start Agent Session**

- **Primary Actor:** Owner
- **Scope:** remote-agents (Backend + Web Interface)
- **Level:** User-Goal
- **Stakeholders and Interests:**
  - Owner: wants a fresh Agent ready to receive instructions against a chosen Repository.
  - Backend: wants exactly one Agent subprocess per Live Session and no orphaned processes.
  - pi.dev: wants the new Session persisted to its session directory as JSONL.
- **Preconditions:**
  - Owner is connected to the Tailnet.
  - The Workspace contains at least one Repository.
  - The Backend is running and `pi` is installed on the Host.
- **Minimal Guarantees:**
  - If start fails, no Live Session appears in the Live list and no orphan subprocess remains.
- **Success Guarantees:**
  - A Live Session exists with a Session ID, bound to the chosen Repository, with the Agent ready to accept a prompt.
  - The Session appears in the Live list and its JSONL file exists on disk.
- **Trigger:** Owner requests a new Session from the Web Interface.

**Main Success Scenario (MSS):**
1. Owner selects a Repository from the Workspace.
2. Owner optionally provides a Session Name.
3. Backend spawns an Agent subprocess with the Repository as its working directory per BR-4.
4. Backend establishes the RPC Channel and waits for the Agent's initial state event carrying the Session ID.
5. Backend registers the Live Session and, if provided, applies the Session Name.
6. System presents the Session's conversation view to the Owner, ready for input.

**Extensions:**
- 1a. System detects the Workspace contains no Repository:
  - 1a1. System reports the empty Workspace.
  - 1a2. Use case ends in failure.
- 3a. Backend detects the Agent subprocess exits before producing its initial state:
  - 3a1. Backend tears down the subprocess and any partial registration.
  - 3a2. System reports the failure to the Owner.
  - 3a3. Use case ends in failure.
- 4a. Backend detects RPC framing errors (non-JSONL input from Agent):
  - 4a1. Backend terminates the subprocess per BR-8.
  - 4a2. System reports the failure to the Owner.
  - 4a3. Use case ends in failure.

**Technology and Data Variations:**
- 1: Repository selection may be presented as a list of immediate subdirectories of the Workspace.
- 3: Spawn arguments include `--mode rpc`, a Workspace-scoped `--session-dir`, and the Repository as `cwd`.
- 5: The Session Name is applied via the `set_session_name` RPC command.

---

**Use Case 2: Resume Live Session**

- **Primary Actor:** Owner
- **Scope:** remote-agents (Backend + Web Interface)
- **Level:** User-Goal
- **Stakeholders and Interests:**
  - Owner: wants to pick up an ongoing Agent interaction from a different device.
  - Backend: wants concurrent viewers of the same Session to observe consistent event order.
- **Preconditions:**
  - Owner is connected to the Tailnet.
  - At least one Live Session exists.
- **Minimal Guarantees:**
  - Attaching a viewer never alters Agent state.
- **Success Guarantees:**
  - Owner sees the current conversation, streamed events, and pending queue of the chosen Session and can send prompts or steering messages.
- **Trigger:** Owner opens the Web Interface and selects a Live Session.

**Main Success Scenario (MSS):**
1. Owner opens the Web Interface.
2. System presents the Live Session list.
3. Owner selects a Live Session.
4. Backend opens a viewer channel to the chosen Session and replays its current state to the browser.
5. Backend forwards subsequent Agent events to the browser as they arrive.
6. Owner inspects Agent output and resumes interaction.

**Extensions:**
- 2a. System detects no Live Sessions exist:
  - 2a1. System presents the Cold Session list per UC-5 and offers Start Agent Session (UC-1).
  - 2a2. Use case ends in success with no Session attached.
- 3a. Backend detects the selected Session ended between listing and selection:
  - 3a1. System reports the Session is no longer Live and offers to resume it cold per UC-3.
  - 3a2. Use case returns to step 2.
- 5a. Owner submits a prompt while the Agent is streaming:
  - 5a1. Backend forwards the prompt as a steering message rather than a fresh prompt.
  - 5a2. Use case returns to step 5.

**Technology and Data Variations:**
- 4: Current state is obtained via `get_state` and `get_messages` over the RPC Channel.
- 5: Events streamed include `message_update`, `tool_execution_*`, `turn_*`, and `queue_update`.

---

**Use Case 3: Resume Cold Session**

- **Primary Actor:** Owner
- **Scope:** remote-agents (Backend + Web Interface)
- **Level:** User-Goal
- **Stakeholders and Interests:**
  - Owner: wants to continue a Session whose Agent process is no longer running (e.g. after Host reboot).
  - Backend: wants exactly one Agent attached to a given Session ID per BR-3.
- **Preconditions:**
  - Owner is connected to the Tailnet.
  - A Cold Session exists on disk for the chosen Session ID.
- **Minimal Guarantees:**
  - If rehydration fails, the Session remains Cold and no orphan subprocess remains.
- **Success Guarantees:**
  - The chosen Session becomes Live with the original Session ID preserved and full conversation history available.
- **Trigger:** Owner selects a Cold Session from the Web Interface.

**Main Success Scenario (MSS):**
1. Owner opens the Web Interface and selects a Cold Session.
2. Backend resolves the Session's Repository binding per BR-4.
3. Backend spawns an Agent subprocess with that Repository as its working directory and the Session ID supplied for resume.
4. Backend establishes the RPC Channel and confirms the Session ID matches.
5. Backend promotes the Session to Live and presents the conversation view to the Owner.

**Extensions:**
- 1a. System detects another browser already attached and the Session is already Live:
  - 1a1. System redirects the Owner into UC-2 for that Live Session.
  - 1a2. Use case ends in success via UC-2.
- 2a. Backend cannot resolve the original Repository (renamed or removed):
  - 2a1. System reports the missing Repository and offers Workspace re-selection.
  - 2a2. Owner selects a replacement Repository or cancels.
  - 2a3. If cancelled, use case ends in failure.
- 4a. Backend detects the Session ID returned by the Agent does not match the requested one:
  - 4a1. Backend terminates the subprocess per BR-8.
  - 4a2. System reports the mismatch.
  - 4a3. Use case ends in failure.

**Technology and Data Variations:**
- 3: Resume is performed via `pi --mode rpc --session <id>` against the Workspace-scoped `--session-dir`.

---

**Use Case 4: Steer or Terminate Live Session**

- **Primary Actor:** Owner
- **Scope:** remote-agents (Backend + Web Interface)
- **Level:** User-Goal
- **Stakeholders and Interests:**
  - Owner: wants to course-correct or stop a running Agent without losing the Session record.
  - Backend: wants the Agent subprocess and its RPC Channel disposed cleanly together.
- **Preconditions:**
  - Owner is connected to the Tailnet.
  - The target Session is Live.
- **Minimal Guarantees:**
  - Steering messages either reach the Agent or surface a delivery error to the Owner; they are never silently dropped.
  - Termination either leaves the Session fully Live or fully Cold; no Live entry without a running subprocess remains.
- **Success Guarantees:**
  - Steering: the Agent receives the message according to `steeringMode`.
  - Termination: the Agent subprocess is gone and the Session is Cold with its JSONL file preserved.
- **Trigger:** Owner sends a steering message or requests termination on a Live Session.

**Main Success Scenario (MSS) — Steer:**
1. Owner is attached to a Live Session per UC-2.
2. Owner submits a steering message.
3. Backend forwards the message over the RPC Channel using `steer` or `follow_up` per current mode.
4. Backend confirms acceptance to the Owner via the resulting `queue_update` event.
5. Owner observes the Agent applying the steering in subsequent events.

**Main Success Scenario (MSS) — Terminate:**
1. Owner selects a Live Session and requests termination.
2. Owner confirms intent.
3. Backend sends `abort` over the RPC Channel, then closes stdin.
4. Backend waits up to the termination timeout for graceful exit, then signals the subprocess.
5. Backend demotes the Session to Cold and confirms termination to the Owner.

**Extensions:**
- 3a (Steer). Backend detects the Agent is not streaming and no steering is applicable:
  - 3a1. Backend delivers the message as a fresh `prompt` instead.
  - 3a2. Use case returns to step 4.
- 4a (Terminate). Backend detects the Agent does not exit within the termination timeout:
  - 4a1. Backend force-kills the subprocess.
  - 4a2. Use case returns to step 5.
- 1a (Terminate). Backend detects the Session ended before the request was issued:
  - 1a1. System reports the Session is already Cold.
  - 1a2. Use case ends in success.

**Technology and Data Variations:**
- 3 (Steer): Command selection follows the RPC contract — `steer` while streaming, `follow_up` for post-turn delivery, `prompt` when idle.
- 4 (Terminate): Graceful shutdown is `abort` then stdin close; escalation is `SIGTERM` then `SIGKILL`.

---

**Use Case 5: Survey Sessions**

- **Primary Actor:** Owner
- **Scope:** remote-agents (Backend + Web Interface)
- **Level:** User-Goal
- **Stakeholders and Interests:**
  - Owner: wants a single view of every Session — Live or Cold — with enough metadata to choose one.
- **Preconditions:**
  - Owner is connected to the Tailnet.
- **Minimal Guarantees:**
  - Live entries reflect Backend reality at request time.
  - Cold entries reflect the on-disk session directory at request time.
- **Success Guarantees:**
  - Owner sees two grouped lists — Live and Cold — each item showing Session Name (if any), Session ID, bound Repository, and last-activity timestamp.
- **Trigger:** Owner opens the Web Interface root.

**Main Success Scenario (MSS):**
1. Owner opens the Web Interface root.
2. Backend enumerates Live Sessions from its in-memory registry.
3. Backend enumerates Cold Sessions by scanning the Workspace-scoped session directory.
4. Backend excludes Session IDs already present in the Live set from the Cold set.
5. System renders both lists grouped by Repository.
6. Owner reads the list and chooses to start (UC-1), resume Live (UC-2), resume Cold (UC-3), or steer/terminate (UC-4).

**Extensions:**
- 3a. Backend detects the session directory is unreadable:
  - 3a1. System renders the Live list only and reports the Cold enumeration failure.
  - 3a2. Use case ends in success with degraded data.
- 2a. Backend detects a Live registry entry whose subprocess is no longer alive:
  - 2a1. Backend demotes the entry to Cold before rendering.
  - 2a2. Use case returns to step 3.

**Technology and Data Variations:**
- 3: Cold enumeration parses the headers of each JSONL file under `~/.pi/agent/sessions/<workspace>/` to extract Session ID, Session Name, and last-modified time.
- 5: Grouping by Repository may render as nested lists, tabs, or sections without changing behavior.
