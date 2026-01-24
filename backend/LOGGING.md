# Logging Guide

## Overview

The backend uses **loguru** for structured, beautiful logging with special highlighting for tool invocations in development mode.

## Features

### Development Mode (Console)
Colored, readable output with special formatting for:
- **🔧 TOOL** - Tool invocations (magenta/bold)
- **✓ DONE** - Successful completions (green/bold)
- **✗ FAIL** - Failed operations (red/bold)
- **Standard logs** - Regular application logs with color-coded levels

### Production Mode (JSON)
Structured JSON output for log aggregation systems like CloudWatch, Datadog, etc.

## Color Scheme

In development mode, logs are color-coded for easy visual scanning:

- **Timestamps** - Green
- **Tool Invocations (🔧 TOOL)** - Bold Magenta with tool emoji
- **Completions (✓ DONE)** - Bold Green with checkmark
- **Failures (✗ FAIL)** - Bold Red with X mark
- **Module/Function Names** - Cyan
- **Context Fields** - Yellow (parameters, results, errors)
- **Log Levels**:
  - DEBUG - Cyan
  - INFO - Default/White
  - WARNING - Yellow
  - ERROR - Red
  - CRITICAL - Bold Red

## Log Format Examples

All logs follow this structure:
```
[Timestamp] | [Type/Level] | [Location] | [Message] | [Context]
```

Where:
- **Timestamp** - ISO format with milliseconds
- **Type/Level** - Either a special type (🔧 TOOL, ✓ DONE, ✗ FAIL) or log level (INFO, WARNING, ERROR)
- **Location** - module:function:line for standard logs, module:function for tools
- **Message** - The log message (snake_case)
- **Context** - Key-value pairs of additional data

### Tool Invocation (Bold Magenta)
```
2026-01-16 11:59:39.742 | 🔧 TOOL   | app.agents.tools.web_search:web_search | web_search_tool_invoked | query='Python async', max_results=5
```

### Tool Completion (Bold Green)
```
2026-01-16 11:59:39.742 | ✓ DONE   | app.agents.tools.web_search:web_search | web_search_completed | results_count=5
```

### Tool Failure (Bold Red)
```
2026-01-16 11:59:39.742 | ✗ FAIL   | app.agents.tools.browser_use:browser_use | browser_use_failed | error='Connection timeout'
```

### Standard Logs
```
2026-01-16 11:59:39.742 | INFO     | app.main:lifespan:27 | application_starting | app_name='HyperAgent'
2026-01-16 11:59:39.742 | WARNING  | app.services.search:search:94 | rate_limit_approaching | usage=85%
2026-01-16 11:59:39.742 | ERROR    | app.api.query:process:156 | request_failed | status=500
```

### Example Session
Here's what a typical agent workflow looks like in the logs:

```
2026-01-16 12:00:00.100 | INFO     | app.api.query:process_query:45 | request_received | user_id=123, query='Find Python tutorials'
2026-01-16 12:00:00.150 | 🔧 TOOL   | app.agents.tools.web_search:web_search | web_search_tool_invoked | query='Python tutorials 2026', max_results=10, search_depth='advanced'
2026-01-16 12:00:02.340 | ✓ DONE   | app.agents.tools.web_search:web_search | web_search_completed | results_count=10, duration_ms=2190
2026-01-16 12:00:02.500 | INFO     | app.agents.subagents.research:analyze | analyzing_results | result_count=10
2026-01-16 12:00:03.200 | 🔧 TOOL   | app.agents.tools.browser_use:browser_use | browser_use_tool_invoked | task='Extract tutorial content from top result', headless=True
2026-01-16 12:00:08.450 | ✓ DONE   | app.agents.tools.browser_use:browser_use | browser_use_completed | extracted_bytes=15234
2026-01-16 12:00:08.500 | INFO     | app.api.query:process_query:78 | response_ready | duration_ms=8400
```

The color coding makes it easy to:
- Spot when tools are invoked (magenta)
- See when operations complete successfully (green)
- Identify failures quickly (red)
- Track the flow of execution through standard INFO logs

## Usage in Code

### Basic Logging
```python
from app.core.logging import get_logger

logger = get_logger(__name__)

# Simple message
logger.info("user_authenticated")

# With context
logger.info("request_completed", user_id=123, duration_ms=250)

# Error with context
logger.error("database_query_failed", table="users", error=str(e))
```

### Tool Invocation Logging
Tool invocations are automatically highlighted when message names end with `_tool_invoked`:

```python
logger.info(
    "web_search_tool_invoked",
    query=query,
    max_results=max_results,
    search_depth=search_depth,
)
```

### Tool Completion Logging
Completions are highlighted when message names end with `_completed`:

```python
logger.info(
    "web_search_completed",
    query=query,
    results_count=len(results),
)
```

### Tool Failure Logging
Failures are highlighted when message names end with `_failed`:

```python
logger.error(
    "web_search_failed",
    query=query,
    error=str(e),
)
```

## Configuration

Configure logging in your environment:

```bash
# Development (colored console)
LOG_LEVEL=DEBUG
LOG_FORMAT=console

# Production (JSON)
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Best Practices

### 1. Use Structured Field Names
Use snake_case for field names and be consistent:
```python
# Good
logger.info("user_registered", user_id=123, email="user@example.com")

# Bad
logger.info("User registered: 123 - user@example.com")
```

### 2. Tool Naming Convention
For tools, follow this pattern:
```python
# Invocation: <tool_name>_tool_invoked
logger.info("web_search_tool_invoked", query=query)

# Completion: <tool_name>_completed or <action>_completed
logger.info("web_search_completed", results_count=5)

# Failure: <tool_name>_failed or <action>_failed
logger.error("web_search_failed", error=str(e))
```

### 3. Context Fields
Include relevant context in every log:
```python
logger.info(
    "llm_request_completed",
    model="claude-3-sonnet",
    tokens=1234,
    duration_ms=456,
)
```

### 4. Exception Logging
Use `logger.exception()` to automatically capture tracebacks:
```python
try:
    result = risky_operation()
except Exception as e:
    logger.exception("operation_failed", operation="risky_operation")
```

## JSON Output Example

In production mode (`LOG_FORMAT=json`), logs are output as JSON:

```json
{
  "text": "web_search_tool_invoked\n",
  "record": {
    "timestamp": "2026-01-16T11:56:48.957089+08:00",
    "level": "INFO",
    "logger": "app.agents.tools.web_search",
    "message": "web_search_tool_invoked",
    "function": "web_search",
    "line": 51,
    "query": "Python async best practices",
    "max_results": 5,
    "search_depth": "basic"
  }
}
```

## Viewing Logs

### Local Development
```bash
# Start the server
uv run uvicorn app.main:app --reload

# Tool invocations will be highlighted in magenta
# Completions in green
# Failures in red
```

### Production
```bash
# Tail logs
tail -f /var/log/hyperagent/app.log

# Search for tool invocations
grep "tool_invoked" /var/log/hyperagent/app.log | jq .

# Monitor failures
grep "failed" /var/log/hyperagent/app.log | jq '.record | {message, error}'
```

## Migration from structlog

The API is compatible with the previous structlog setup:
- `setup_logging()` - Same function signature
- `get_logger(__name__)` - Same usage pattern
- Structured field passing - Same syntax

No code changes required in existing files!
