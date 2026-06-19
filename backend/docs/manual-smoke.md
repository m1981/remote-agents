# Manual Smoke Test — M3.3

Test the backend against **real** `pi --mode rpc`.

## Prerequisites

- `pi` installed and working: `pi --version`
- A test repository (can be the remote-agents repo itself)

## Setup

```bash
cd /Users/michal/PycharmProjects/remote-agents/backend

# Start the backend with real pi
export PI_WORKSPACE=/Users/michal/PycharmProjects
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

## Test 1: Health check

```bash
curl http://localhost:8080/health
# Expected: {"status":"ok"}
```

## Test 2: List repos

```bash
curl http://localhost:8080/repos
# Expected: {"repos":["remote-agents",...]}
```

## Test 3: Spawn a session

```bash
curl -X POST http://localhost:8080/sessions \
  -H "Content-Type: application/json" \
  -d '{"repo":"remote-agents","name":"test-session"}'
# Expected: {"session_id":"some-uuid"}
```

Save the session_id for later tests.

## Test 4: List sessions

```bash
curl http://localhost:8080/sessions
# Expected: {"live":[{"session_id":"...","repo":"remote-agents",...}],"cold":[]}
```

## Test 5: WebSocket connection

Install wscat if needed:
```bash
npm install -g wscat
```

Connect to the session:
```bash
wscat -c ws://localhost:8080/ws/sessions/<SESSION_ID>
```

Expected: You should receive a snapshot message:
```json
{"kind":"snapshot","state":{...},"messages":[...]}
```

## Test 6: Send a prompt via WebSocket

In the wscat session, send:
```json
{"type":"prompt","message":"Hello, what is 2+2?"}
```

Expected: You should see streamed events:
```json
{"kind":"event","event":{"type":"agent_start"}}
{"kind":"event","event":{"type":"turn_start"}}
{"kind":"event","event":{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"4"}}}
...
{"kind":"event","event":{"type":"agent_end","messages":[...]}}
```

## Test 7: Terminate a session

```bash
curl -X POST http://localhost:8080/sessions/<SESSION_ID>/terminate
# Expected: {"status":"terminated"}
```

## Checklist

- [ ] Health endpoint returns 200
- [ ] Repos endpoint lists workspace subdirs
- [ ] Can spawn a session with real pi
- [ ] Sessions list shows live session
- [ ] WebSocket connects and receives snapshot
- [ ] Can send prompt and receive streamed events
- [ ] Can terminate a session
- [ ] Session moves to cold list after termination
