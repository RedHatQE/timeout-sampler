# Filtering and Handling Exceptions

When polling a function that may intermittently fail, you need to control which exceptions are silently retried, which are matched by message text, and which immediately abort the loop. The `exceptions_dict` parameter gives you fine-grained control over all three behaviors.

## Prerequisites

- `timeout-sampler` installed in your project (see [Getting Started with timeout-sampler](quickstart.html))
- Basic familiarity with creating a polling loop (see [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html))

## Quick Example

```python
from timeout_sampler import TimeoutSampler

# Ignore all ConnectionError exceptions during polling
for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=2,
    func=fetch_data,
    exceptions_dict={ConnectionError: []},
):
    if sample:
        break
```

An empty list `[]` means "ignore this exception regardless of its message text." If `fetch_data()` raises a `ConnectionError`, polling continues. Any other exception type immediately stops the loop.

## How `exceptions_dict` Works

The `exceptions_dict` parameter is a dictionary that maps exception classes to lists of allowed message strings:

```python
exceptions_dict: dict[type[Exception], list[str]] | None
```

| Value | Meaning |
|---|---|
| `{SomeError: []}` | Ignore **all** `SomeError` exceptions (any message) |
| `{SomeError: ["connection refused"]}` | Ignore `SomeError` only when the message **contains** `"connection refused"` |
| `{SomeError: ["timeout", "refused"]}` | Ignore `SomeError` when the message contains `"timeout"` **or** `"refused"` |
| `{}` | Ignore **nothing** — any exception immediately stops polling |
| `None` (or omitted) | Defaults to `{Exception: []}` — ignore all exceptions |

> **Warning:** When you omit `exceptions_dict` entirely, **all** exceptions are silently ignored during polling. Always pass an explicit `exceptions_dict` in production to avoid swallowing unexpected errors.

## Step-by-Step: Common Use Cases

### 1. Ignore a Specific Exception Type

Pass the exception class with an empty list to ignore every instance of that exception:

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=5,
    func=check_service_health,
    exceptions_dict={ConnectionError: []},
):
    if sample == "healthy":
        break
```

### 2. Match by Message Text

Provide one or more substrings in the list. The exception is ignored only when any substring appears in the exception's text:

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=5,
    func=query_api,
    exceptions_dict={
        RuntimeError: ["temporarily unavailable", "rate limit"],
    },
):
    if sample:
        break
```

Here, a `RuntimeError("service temporarily unavailable")` is ignored (substring match), but a `RuntimeError("invalid credentials")` immediately stops polling.

> **Note:** Message matching uses a simple substring check (`msg in str(exception)`), not regex. The match is case-sensitive.

### 3. Handle Multiple Exception Types

Add multiple entries to the dictionary, each with its own message filter:

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=120,
    sleep=10,
    func=deploy_resource,
    exceptions_dict={
        ConnectionError: [],                      # ignore all connection errors
        TimeoutError: [],                         # ignore all timeout errors
        ValueError: ["not ready", "pending"],     # ignore only specific messages
    },
):
    if sample:
        break
```

### 4. Re-raise All Exceptions (No Filtering)

Pass an empty dictionary to ensure any exception immediately stops polling:

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=2,
    func=critical_operation,
    exceptions_dict={},
):
    if sample:
        break
```

### 5. Use with the `@retry` Decorator

The `exceptions_dict` parameter works identically with the `@retry` decorator:

```python
from timeout_sampler import retry

@retry(
    wait_timeout=30,
    sleep=2,
    exceptions_dict={ConnectionError: []},
)
def fetch_data():
    # May raise ConnectionError intermittently
    return api_client.get("/data")
```

See [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html) for full decorator usage.

## Advanced Usage

### Inheritance-Aware Matching

Exception matching respects Python's class hierarchy. When you add a parent exception class to `exceptions_dict`, **all child classes** are also matched:

```python
exceptions_dict = {ConnectionError: []}
```

| Raised Exception | Matched? | Reason |
|---|---|---|
| `ConnectionError` | ✅ Yes | Exact match |
| `ConnectionRefusedError` | ✅ Yes | Subclass of `ConnectionError` |
| `OSError` | ❌ No | Parent class, not a subclass |
| `ValueError` | ❌ No | Unrelated type |

This means you can filter broadly by specifying a base class, or narrowly by specifying a leaf class.

> **Tip:** Use `{Exception: []}` to ignore all exceptions (this is the default when `exceptions_dict` is omitted). Use a specific class like `{KeyError: []}` to only ignore that type and its subclasses.

### Three Outcome Categories

When your polled function raises an exception, exactly one of three things happens:

1. **Exact match or child class, message matches** → exception is ignored, polling continues
2. **Exact match or child class, message does NOT match** → polling stops, `TimeoutExpiredError` is raised immediately
3. **Exception type not in `exceptions_dict`** → polling stops, `TimeoutExpiredError` is raised immediately

For a deeper look at the matching algorithm, see [How Exception Matching Works](exception-matching-logic.html).

### Accessing the Original Exception After Timeout

When polling ends — either by timeout or a non-matching exception — a `TimeoutExpiredError` is raised. The original exception is stored on its `last_exp` attribute:

```python
from timeout_sampler import TimeoutExpiredError, TimeoutSampler

try:
    for sample in TimeoutSampler(
        wait_timeout=10,
        sleep=2,
        func=flaky_function,
        exceptions_dict={ConnectionError: []},
    ):
        if sample:
            break
except TimeoutExpiredError as e:
    print(f"Last exception type: {type(e.last_exp)}")  # e.g. <class 'ConnectionError'>
    print(f"Last exception message: {e.last_exp}")
    print(f"Elapsed time: {e.elapsed_time}")
```

> **Note:** If the function never raised an exception (it just returned falsy values until timeout), `last_exp` is `None`.

See [TimeoutExpiredError Reference](api-exceptions.html) for all available attributes.

### Empty Strings in Message Lists

An empty string in the message list is **not** treated as a wildcard — it is explicitly skipped. Use an empty list `[]` instead to match all messages:

```python
# ❌ WRONG — the empty string "" is ignored, so NO messages match
exceptions_dict = {ValueError: [""]}

# ✅ CORRECT — empty list means "match all messages"
exceptions_dict = {ValueError: []}
```

## Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| All exceptions are swallowed silently | `exceptions_dict` was omitted (defaults to `{Exception: []}`) | Pass an explicit `exceptions_dict` with only the types you want to ignore |
| Exception is not being ignored | The raised exception is a **parent** of the class in `exceptions_dict`, not a child | Add the parent class to `exceptions_dict`, or use a broader base class |
| Message filter doesn't match | Substring matching is case-sensitive | Verify the exact exception message text and case |
| `TimeoutExpiredError` raised immediately despite exception being in dict | The exception message doesn't contain any of the specified substrings | Use `[]` to ignore all messages, or add the correct substring |

## Related Pages

- [How Exception Matching Works](exception-matching-logic.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html)
- [TimeoutSampler API](api-timeout-sampler.html)
