# How Exception Matching Works

When your polled function raises an exception inside a `TimeoutSampler` loop, the sampler must decide: *should it swallow the error and keep retrying, or should it stop immediately?* This decision is made by the **exception matching algorithm** — an inheritance-aware, message-filtered check that gives you precise control over which failures are retried and which are surfaced right away.

Understanding this algorithm helps you avoid two common pitfalls: accidentally retrying an exception you should have surfaced (hiding real bugs), or accidentally re-raising a transient error you meant to ignore (breaking your polling loop too early).

## The Big Picture

Every time an exception is raised inside the function passed to `TimeoutSampler`, the sampler runs through a two-stage decision process:

| Stage | What It Checks | Outcome |
|-------|---------------|---------|
| **1. Type matching** | Is the raised exception an instance of any class listed in `exceptions_dict`? This uses Python's `isinstance()`, so subclass relationships are honored. | If no match → **re-raise immediately** |
| **2. Message filtering** | Does the exception's string representation contain at least one of the allowed message substrings for the matched class? | If match → **ignore and retry**; if no message match → **re-raise immediately** |

If the exception passes both stages, the sampler sleeps and calls the function again. If it fails either stage, the sampler wraps the original exception in a `TimeoutExpiredError` and raises it.

## The Three Outcome Categories

When an exception is raised inside your polled function, exactly one of these three things happens:

### 1. Exact Class Match — Continue Polling

The raised exception's class is explicitly listed as a key in `exceptions_dict`, and the message filter passes (or is empty).

```python
from timeout_sampler import TimeoutSampler

# ValueError is explicitly listed, empty list means "match any message"
exceptions_dict = {ValueError: []}

for sample in TimeoutSampler(
    wait_timeout=10,
    sleep=1,
    func=might_raise_value_error,
    exceptions_dict=exceptions_dict,
):
    if sample:
        break
# Any ValueError is silently retried until timeout
```

### 2. Inherited Class Match — Continue Polling

The raised exception is a *subclass* of a class listed in `exceptions_dict`. The sampler uses `isinstance()` internally, so the full inheritance chain is checked.

```python
# Imagine this hierarchy:
# class AExampleError(Exception): ...
# class BExampleError(AExampleError): ...

exceptions_dict = {AExampleError: []}

# If the function raises BExampleError, it still matches
# because isinstance(BExampleError(), AExampleError) is True
```

### 3. No Match — Re-raise Immediately

The raised exception is neither listed in `exceptions_dict` nor a subclass of any listed class. The sampler wraps it in a `TimeoutExpiredError` and re-raises immediately — it does *not* wait for the timeout to expire.

```python
exceptions_dict = {ValueError: []}

# If the function raises KeyError, it does NOT match ValueError
# and is NOT a subclass of ValueError → re-raised immediately
```

> **Warning:** If you pass an empty `exceptions_dict` (`{}`), **no exceptions will be matched**, so *every* exception will cause an immediate re-raise. This is different from the default behavior (see below).

## How Message Filtering Works

Each key in `exceptions_dict` maps to a list of allowed message substrings. The message filter runs *after* the type match succeeds:

| `exception_messages` value | Behavior |
|---|---|
| `[]` (empty list) | **All messages match.** Any exception of this type is ignored. |
| `["connection refused", "timeout"]` | The exception's `str()` representation must contain at least one of these substrings. |
| `[""]` (list with empty string) | **Nothing matches.** An empty string is explicitly excluded as a safeguard. |

The matching logic is a substring check using Python's `in` operator:

```python
# Internal logic (simplified):
any(msg and msg in str(exp) for msg in exception_messages)
```

### Message Filtering Examples

```python
from timeout_sampler import TimeoutSampler

# Match only ConnectionError with "refused" in the message
exceptions_dict = {ConnectionError: ["refused"]}

# ✅ ConnectionError("Connection refused by host")  → retried (contains "refused")
# ❌ ConnectionError("DNS resolution failed")       → re-raised (no substring match)
# ❌ ValueError("Connection refused")               → re-raised (wrong type)
```

```python
# Match ValueError with ANY of several messages
exceptions_dict = {ValueError: ["not ready", "still loading"]}

# ✅ ValueError("Resource not ready")     → retried
# ✅ ValueError("Page still loading")     → retried
# ❌ ValueError("Invalid input")          → re-raised
```

> **Tip:** Message filters are case-sensitive. `"Refused"` will not match an exception with the message `"connection refused"`. Choose your substrings carefully.

## The Default `exceptions_dict`

If you do not pass an `exceptions_dict` to `TimeoutSampler`, the default value is:

```python
{Exception: []}
```

Since every exception in Python inherits from `Exception`, this means **all exceptions are silently retried** until the timeout expires. This is the most permissive setting.

```python
# These two are equivalent:
TimeoutSampler(wait_timeout=10, sleep=1, func=my_func)
TimeoutSampler(wait_timeout=10, sleep=1, func=my_func, exceptions_dict={Exception: []})
```

> **Note:** The `@retry` decorator also defaults to `{Exception: []}` when `exceptions_dict` is not specified. See [@retry Decorator API](api-retry-decorator.html) for the full parameter list.

## Step-by-Step: What Happens When an Exception Is Raised

1. Your function (`func`) raises an exception `exp`.
2. The sampler records `exp` as `last_exp` and calculates `elapsed_time`.
3. The sampler calls `_should_ignore_exception(exp)`, which iterates over every key in `exceptions_dict`:
   - For each key class, it checks `isinstance(exp, key)`.
   - On the first type match, it retrieves the message list and calls `_is_exception_matched(exp, messages)`.
   - If both type and message match → return `True` (ignore the exception).
4. **If ignored:** the sampler sleeps for `sleep` seconds, then calls `func` again.
5. **If not ignored:** the sampler raises `TimeoutExpiredError`, attaching `exp` as `last_exp` and the current `elapsed_time`.

> **Note:** When an exception is not matched, the `TimeoutExpiredError` is raised **immediately** — the sampler does not wait for the full timeout to expire. This means unrecognized exceptions surface fast.

## Multiple Exception Classes

You can list multiple exception classes in `exceptions_dict`. The sampler checks them in iteration order:

```python
exceptions_dict = {
    ConnectionError: ["refused", "reset"],
    TimeoutError: [],
    ValueError: ["not ready"],
}
```

The first matching class wins. Once a type match is found, only that class's message list is checked. If the message filter fails for that class, the exception is re-raised — the sampler does **not** continue checking other classes in the dict.

> **Warning:** Because `isinstance()` honors inheritance, ordering can matter when your exception classes share a parent-child relationship. If both `AExampleError` and `BExampleError(AExampleError)` are in the dict, the one that appears first during iteration will be checked first. Place more specific (child) classes before more general (parent) classes to ensure the correct message filter is applied.

## How It Affects `TimeoutExpiredError`

When an exception is re-raised (either immediately or at timeout expiry), it is wrapped in a `TimeoutExpiredError`. The original exception is accessible through the `last_exp` attribute:

```python
from timeout_sampler import TimeoutExpiredError, TimeoutSampler

try:
    for sample in TimeoutSampler(
        wait_timeout=5,
        sleep=1,
        func=my_unstable_func,
        exceptions_dict={ConnectionError: []},
    ):
        if sample:
            break
except TimeoutExpiredError as e:
    print(e.last_exp)       # The original exception (e.g., ConnectionError)
    print(e.elapsed_time)   # Seconds elapsed before the error
```

See [TimeoutExpiredError Reference](api-exceptions.html) for the full attribute and method reference.

## Quick Reference Table

| Scenario | `exceptions_dict` | Raised Exception | Result |
|---|---|---|---|
| Default — catch all | `{Exception: []}` | Any exception | Retry until timeout |
| Specific type, any message | `{ValueError: []}` | `ValueError("anything")` | Retry |
| Specific type, filtered message | `{ValueError: ["not ready"]}` | `ValueError("not ready yet")` | Retry |
| Specific type, wrong message | `{ValueError: ["not ready"]}` | `ValueError("bad input")` | Re-raise immediately |
| Subclass match | `{Exception: []}` | `ValueError()` | Retry (ValueError inherits Exception) |
| Parent does not match child | `{ValueError: []}` | `Exception()` | Re-raise immediately |
| Empty dict — catch nothing | `{}` | Any exception | Re-raise immediately |

## Related Pages

- [Filtering and Handling Exceptions](handling-exceptions.html) — practical guide to configuring `exceptions_dict` for common scenarios
- [TimeoutSampler API](api-timeout-sampler.html) — full constructor parameters and iteration behavior reference
- [TimeoutExpiredError Reference](api-exceptions.html) — attributes and string representation of the error raised on timeout or unmatched exceptions
- [@retry Decorator API](api-retry-decorator.html) — how `exceptions_dict` is passed through the decorator
- [Common Polling Patterns](common-polling-patterns.html) — copy-paste recipes combining exception filters with polling strategies

## Related Pages

- [Filtering and Handling Exceptions](handling-exceptions.html)
- [TimeoutSampler API](api-timeout-sampler.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
- [@retry Decorator API](api-retry-decorator.html)
- [Common Polling Patterns](common-polling-patterns.html)
