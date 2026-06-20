# Session 019ee709 Debug Summary

## Quick Diagnosis

**Problem:** User messages appear but agent responses don't.

**Root Cause:** Pi agent receives the prompt but generates **zero events** afterward. Most likely:
1. Model API failure (opencode-go / mimo-v2.5-pro)
2. **Stderr pipe full** (code bug - now fixed)
3. Process crash

## Critical Bug Found & Fixed

### Bug: stderr Never Read

**File:** `backend/app/rpc/agent_process.py`

**Problem:** stderr was captured but never read. If pi wrote errors to stderr:
1. Pipe buffer fills (64KB)
2. Pi blocks on stderr write
3. Pi stops generating stdout events
4. System hangs silently

**Fix Applied:** Added `_read_stderr()` background task to drain stderr and log it.

### Changes Made

```python
# 1. Added _stderr_task to __init__
self._stderr_task: asyncio.Task[None] | None = None

# 2. Added _read_stderr() method
async def _read_stderr(self) -> None:
    """Background task: read stderr and log it."""
    assert self._process.stderr is not None
    try:
        async for line in read_jsonl_lines(self._process.stderr):
            logger.warning("pi stderr: %s", line)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("stderr reader error: %s", e)

# 3. Started stderr reader in start_detached()
proc._stderr_task = asyncio.create_task(proc._read_stderr())

# 4. Cancel stderr task in terminate()
if self._stderr_task and not self._stderr_task.done():
    self._stderr_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await self._stderr_task

# 5. Added debug logging in _read_stdout()
logger.debug("pi stdout: %s", line)
```

## Diagnostic Steps

### On the VPS (51.83.199.194)

```bash
# 1. Check backend logs for errors
journalctl --user -u remote-agents -n 200 | grep -E "(error|Error|ERROR|Failed|failed)"

# 2. Check session file
cat ~/.pi/agent/sessions/--srv-workspace-byte-brewery--/*019ee709*.jsonl

# 3. Test pi directly
cd /srv/workspace/byte-brewery
echo '{"type":"prompt","message":"hello"}' | timeout 30 pi --mode rpc --no-session

# 4. Check pi auth
cat ~/.pi/agent/auth.json | python3 -c "import json,sys; print(list(json.load(sys.stdin).keys()))"

# 5. Check pi settings
cat ~/.pi/agent/settings.json
```

### After Deploying Fix

```bash
# 1. Deploy the fix
cd /home/ubuntu/remote-agents
git pull

# 2. Restart service
systemctl --user restart remote-agents

# 3. Monitor stderr output (NEW!)
journalctl --user -u remote-agents -f | grep "pi stderr"

# 4. Test with a new session
# Open browser and send a message
# Check logs for stderr output
```

## Expected Behavior After Fix

### Before Fix (Silent Failure)
```
# No stderr output visible
# 30 second timeout
# Generic error message to client
```

### After Fix (Visible Errors)
```
# Stderr output visible in logs:
Jun 21 12:00:00 remote-agents[12345]: pi stderr: Error: API key not found for provider "opencode-go"
Jun 21 12:00:00 remote-agents[12345]: pi stderr: Failed to initialize model: opencode-go/mimo-v2.5-pro
```

## Sequence Diagram

See `debug-session-019ee709.md` for the full Mermaid sequence diagram showing:
- WebSocket connection flow
- Snapshot retrieval
- Event forwarding setup
- Prompt command flow
- **Critical failure point in Phase 5**
- Timeout behavior
- Stderr issue

## Files Modified

1. `backend/app/rpc/agent_process.py`
   - Added `_read_stderr()` method
   - Added `_stderr_task` initialization
   - Added stderr reader startup in `start_detached()`
   - Added stderr task cancellation in `terminate()`
   - Added debug logging in `_read_stdout()`

## Tests

All 126 tests pass:
```
======================== 126 passed, 6 warnings in 9.97s ========================
```

## Next Steps

1. **Deploy the fix** to the VPS
2. **Check stderr logs** for pi error messages
3. **Verify pi configuration** (auth.json, settings.json)
4. **Test pi directly** to confirm it can reach the model API
5. **Create a new session** and verify responses appear

## Additional Recommendations

### 1. Add Missing Event Types

The code is missing these pi RPC event types:
- `tool_execution_update`
- `compaction_start` / `compaction_end`
- `auto_retry_start` / `auto_retry_end`
- `extension_error`

### 2. Add Health Check Endpoint

```python
@router.get("/sessions/{session_id}/health")
async def session_health(session_id: str):
    # Return process status, pid, returncode
```

### 3. Add Periodic Health Checks

Monitor agent processes and detect stuck prompts before the 30-second timeout.

### 4. Add Event Logging Toggle

Allow enabling/disabling stdout/stderr logging for debugging without code changes.

