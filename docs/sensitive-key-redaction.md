# Redacting Sensitive Data from Log Output

When polling functions that handle credentials, API keys, or other secrets, you need to ensure those values never leak into your application logs. The `sensitive_keys` parameter lets you control exactly which argument keys are masked in log output from both `TimeoutSampler` and `@retry`.

## Prerequisites

- `timeout-sampler` installed in your project
- Basic familiarity with `TimeoutSampler` or the `@retry` decorator (see [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html) or [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html))

## Quick Example

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=5,
    func=call_api,
    headers={"Authorization": "Bearer my-secret-token", "Content-Type": "application/json"},
):
    if sample:
        break
```

The log output automatically masks the `Authorization` value:

```
Kwargs: {'headers': {'Authorization': '***', 'Content-Type': 'application/json'}}
```

No configuration needed — `Authorization` is one of the built-in sensitive keys.

## Built-in Default Sensitive Keys

The following keys are redacted automatically, with no extra configuration:

| Key              | Common Use                          |
|------------------|-------------------------------------|
| `authorization`  | HTTP Authorization headers          |
| `token`          | OAuth/session tokens                |
| `access_token`   | OAuth2 access tokens                |
| `password`       | User/service credentials            |
| `secret`         | Shared secrets                      |
| `api_key`        | API keys                            |
| `apikey`         | API keys (alternate spelling)       |

> **Note:** Matching is **case-insensitive** and uses **exact key name** comparison. A key named `Authorization` or `AUTHORIZATION` will be redacted, but a key like `nextPageToken` or `token_count` will **not** — only a key named exactly `token` (in any case) triggers redaction.

## Adding Custom Sensitive Keys

Pass a `set` or `frozenset` of additional key names to the `sensitive_keys` parameter:

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=call_api,
    sensitive_keys=frozenset({"x-custom-secret"}),
    headers={"Authorization": "Bearer token", "x-custom-secret": "value"}, # pragma: allowlist secret
):
    if sample:
        break
```

The log output redacts both the built-in key and your custom key:

```
Kwargs: {'headers': {'Authorization': '***', 'x-custom-secret': '***'}}
```

Custom keys are **merged** with the defaults — you never lose the built-in protection. Custom key matching is also case-insensitive: `"X-My-Token"` will match `x-my-token`, `X-MY-TOKEN`, etc.

### Using `sensitive_keys` with `@retry`

The `@retry` decorator accepts the same parameter:

```python
from timeout_sampler import retry

@retry(
    wait_timeout=30,
    sleep=2,
    sensitive_keys=frozenset({"x-api-secret", "session_id"}),
)
def fetch_data(headers=None, session_id=None):
    # Both headers containing default sensitive keys AND session_id will be redacted
    return make_request(headers=headers, session_id=session_id)

fetch_data(
    headers={"Authorization": "Bearer abc123"},
    session_id="sess-xyz-999",
)
```

See [@retry Decorator API](api-retry-decorator.html) for the full parameter reference.

### Passing an Empty Set

Passing an empty `frozenset` or `set` still preserves all built-in defaults — it does not disable redaction:

```python
# Built-in keys are still redacted
sampler = TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=call_api,
    sensitive_keys=frozenset(),  # defaults still active
    headers={"Authorization": "Bearer still-redacted"},
)
```

## How Recursive Redaction Works

Redaction isn't limited to top-level keyword arguments. It walks through your data **recursively**, masking sensitive keys inside nested structures:

### Nested Dictionaries

```python
TimeoutSampler(
    wait_timeout=10,
    sleep=1,
    func=process,
    config={"database": {"password": "hunter2", "host": "db.example.com"}}, # pragma: allowlist secret
)
# Logged as: Kwargs: {'config': {'database': {'password': '***', 'host': 'db.example.com'}}}
```

### Lists Containing Dictionaries

```python
TimeoutSampler(
    wait_timeout=10,
    sleep=1,
    func=process,
    args_list=[{"token": "secret-in-list", "id": 42}],
)
# Logged as: Kwargs: {'args_list': [{'token': '***', 'id': 42}]}
```

### Tuples Containing Dictionaries

Tuples are traversed the same way as lists — any dictionary found inside a tuple has its sensitive keys redacted.

### Positional Arguments

Dictionaries passed as positional arguments via `func_args` are also redacted:

```python
TimeoutSampler(
    wait_timeout=10,
    sleep=1,
    func=send_request,
    func_args=({"Authorization": "Bearer pos-secret", "safe": "visible"},),
)
# Logged as: Args: ({'Authorization': '***', 'safe': 'visible'},)
```

### Non-String Dictionary Keys

Dictionaries with non-string keys (integers, tuples, etc.) are handled safely. Only string keys are checked for sensitive matches — non-string keys are passed through unchanged:

```python
TimeoutSampler(
    wait_timeout=10,
    sleep=1,
    func=process,
    data={1: "int-key-value", "password": "secret123"}, # pragma: allowlist secret
)
# Logged as: Kwargs: {'data': {1: 'int-key-value', 'password': '***'}}
```

## Advanced Usage

### Disabling Argument Logging Entirely

If you prefer to suppress all argument output rather than relying on selective redaction, set `print_func_args=False`:

```python
TimeoutSampler(
    wait_timeout=60,
    sleep=5,
    func=call_api,
    print_func_args=False,
    headers={"Authorization": "Bearer secret"},
)
# Log output contains no Args/Kwargs section at all
```

See [Controlling Log Output](controlling-logging.html) for more logging options.

### Depth Limit for Nested Data

Redaction traverses up to **20 levels** of nesting. Data nested beyond this depth is replaced with a sentinel value instead of being logged:

```
<redacted: max depth exceeded>
```

This protects against stack overflows from extremely deep or circular data structures. In practice, 20 levels is far deeper than any typical API payload.

### Type Validation on `sensitive_keys`

The `sensitive_keys` parameter must contain **only strings**. Passing non-string values raises a `TypeError` immediately at construction time:

```python
# Raises TypeError: sensitive_keys must contain only strings, got int: 123
TimeoutSampler(
    wait_timeout=10,
    sleep=1,
    func=call_api,
    sensitive_keys=frozenset({123, "valid_key"}),
)
```

> **Tip:** Validate your `sensitive_keys` values early. Errors are raised at `TimeoutSampler` or `@retry` initialization — not when log output is generated — so you'll catch mistakes before any polling begins.

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| A key like `nextPageToken` is unexpectedly redacted | Custom `sensitive_keys` contains a key that partially matches | Redaction uses **exact** key name matching (case-insensitive). Check your `sensitive_keys` set for overly broad entries. |
| Sensitive values still appear in logs | The key name isn't in the default set or your custom set | Add the key to `sensitive_keys`. Only exact key-name matches are redacted. |
| `TypeError` when constructing the sampler | Non-string value in `sensitive_keys` | Ensure all elements in the set are strings. |
| `<redacted: max depth exceeded>` appears in logs | Data structure is nested more than 20 levels deep | This is expected safety behavior. Restructure data or disable argument logging with `print_func_args=False`. |
| No kwargs visible at all in logs | `print_func_args` is set to `False` | Set `print_func_args=True` (the default) to see redacted argument output. |

## Related Pages

- [Controlling Log Output](controlling-logging.html)
- [TimeoutSampler API](api-timeout-sampler.html)
- [@retry Decorator API](api-retry-decorator.html)
- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html)
