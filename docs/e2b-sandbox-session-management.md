# E2B Sandbox Session Management

## Overview

HyperAgent implements **session-based sandbox reuse** to optimize e2b sandbox usage and maintain state across multiple tool calls within the same conversation.

## How It Works

### Session Key Format

Both execution and desktop sandboxes use the same session key format:
```
{user_id}:{task_id}
```

### Task ID Resolution

The backend automatically determines the `task_id` using this priority order:

1. **Explicit `task_id`** from request (if provided)
2. **`conversation_id`** from request (fallback)
3. **Generated UUID** (if neither provided)

**Source:** `backend/app/api/query.py:372`
```python
chat_task_id = request.task_id or request.conversation_id or str(uuid.uuid4())
```

### Session Lifecycle

1. **First request in conversation:**
   - New sandbox created
   - Session stored with key: `{user_id}:{conversation_id}`
   - Session timeout starts (10-15 minutes)

2. **Subsequent requests in same conversation:**
   - Same `conversation_id` → same session key
   - Existing sandbox retrieved and reused
   - Health check performed (`echo` command)
   - Session timeout refreshed

3. **Session expiration:**
   - Background cleanup runs every 60 seconds
   - Sessions idle for >10-15 minutes are cleaned up
   - Sandbox closed and removed from memory

## Recent Fix (2026-01-24)

### Problem

Local conversations (created when user is not authenticated or backend is unavailable) were NOT reusing sandboxes.

**Root cause:** Frontend was filtering out local conversation IDs before sending to backend:
```typescript
// OLD - Incorrect behavior
conversation_id: conversationId?.startsWith("local-") ? null : conversationId
```

This caused:
- `conversation_id` sent as `null` for local conversations
- Backend generated new UUID for each request
- **New sandbox created every time!**

### Solution

**Always send `conversation_id`**, regardless of whether it's local or remote:

```typescript
// NEW - Correct behavior
conversation_id: conversationId
```

**Files changed:**
- `web/components/query/chat-interface.tsx` (2 locations)
  - Line ~693: `handleChat` function
  - Line ~1077: `handleAgentTask` function

## Implementation Details

### Sandbox Managers

**Execution Sandbox Manager** (`backend/app/sandbox/execution_sandbox_manager.py`)
- Manages code execution sandboxes (Python, JS, Bash)
- Session timeout: 10 minutes (configurable via `e2b_session_timeout_minutes`)
- Health check: Simple `echo` command

**Desktop Sandbox Manager** (`backend/app/sandbox/desktop_sandbox_manager.py`)
- Manages browser automation sandboxes
- Session timeout: 15 minutes (configurable via `e2b_desktop_session_timeout_minutes`)
- Health check: Browser connectivity test
- Stream management for live browser viewing

### Configuration

Environment variables in `backend/app/config.py`:

```python
# Execution Sandbox
e2b_api_key: str = ""
e2b_template_id: str = ""  # Optional custom template
e2b_code_timeout: int = 300  # 5 minutes
e2b_session_timeout_minutes: int = 10

# Desktop Sandbox
e2b_desktop_timeout: int = 900  # 15 minutes
e2b_desktop_session_timeout_minutes: int = 15
e2b_desktop_stream_ready_wait_ms: int = 3000
```

### Metrics

Get sandbox metrics via:
```python
from app.sandbox import get_sandbox_metrics

metrics = get_sandbox_metrics()
# Returns:
{
    "execution": {
        "active_sessions": int,
        "total_created": int,
        "total_cleaned": int,
        "total_reused": int,
        "health_check_failures": int,
    },
    "desktop": { ... },
    "totals": { ... }
}
```

## Benefits

1. **Cost Optimization**
   - Reduced sandbox creation overhead
   - Lower API costs from e2b
   - Fewer cold starts

2. **Performance**
   - Instant sandbox availability for subsequent requests
   - No setup delay for repeated tool calls
   - Persistent file system within session

3. **User Experience**
   - Files persist across code execution calls
   - Faster response times
   - Consistent environment state

## Troubleshooting

### Sandbox not reusing

**Check 1:** Verify `conversation_id` is being sent
```bash
# In browser dev tools network tab, check request payload
{
  "conversation_id": "abc-123-def",  # Should NOT be null
  "message": "...",
  ...
}
```

**Check 2:** Verify session key format
```python
# In backend logs, look for:
[ExecutionSandboxManager] Session key: user123:conv-abc-123
```

**Check 3:** Check session timeout
```python
# Sessions expire after 10-15 minutes of inactivity
# Increase timeout if needed:
e2b_session_timeout_minutes=30  # For execution
e2b_desktop_session_timeout_minutes=45  # For desktop
```

### Health check failures

If health checks are failing frequently, check:
1. Network connectivity to e2b service
2. Sandbox resource limits
3. E2B API key validity

## Future Enhancements

Potential improvements to consider:

1. **Persistent sandboxes across conversations**
   - Share sandbox across multiple conversations for same user
   - Requires namespace isolation

2. **Smart session timeout**
   - Extend timeout based on usage patterns
   - Proactive cleanup of idle sessions

3. **Sandbox pooling**
   - Pre-warm sandbox pool for faster first request
   - Reduced cold start latency

4. **Session migration**
   - Transfer sandbox between conversations
   - Preserve state when conversation is archived
