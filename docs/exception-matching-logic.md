# How Exception Matching Works

When your polled function raises an exception inside a `TimeoutSampler` loop, the sampler must decide: *should it swallow the error and keep retrying, or should it stop immediately?* This decision is made by the **exception matching algorithm** — an inheritance-aware, message-filtered check that gives you precise control over which failures are retried and which are surfaced right away.

Understanding this algorithm helps you avoid two common pitfalls: accidentally retrying an exception you should have surfaced (hiding real bugs), or accidentally re-raising a transient error you meant to ignore (breaking your polling loop too early).

## The Big Picture

Every time an exception is raised inside the function passed to `TimeoutSampler`, the sampler runs through a two-stage decision process:

| Stage | What It Checks | Outcome |
|-------|---------------|---------|
| **1. Type matching** | Is the raised exception an instance of any class listed in `exceptions_dict`? This uses Python's `isinstance()`, so subclass relationships are honored. | If no match → **re-raise immediately** |
| **2. Filter matching** | Does the exception pass at least one filter in the matched class's filter list? Filters can be **substring strings** (checked against `str(exception)`) or **callables** (invoked with the exception, returning a truthy value to ignore). | If match → **ignore and retry**; if no filter match → **re-raise immediately** |

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

## How Filter Matching Works

Each key in `exceptions_dict` maps to a list of **filters**. A filter can be a **string** (substring match against `str(exception)`) or a **callable** (invoked with the exception instance, returning a truthy value to ignore). The filter list is evaluated *after* the type match succeeds:

| Filter list value | Behavior |
|---|---|
| `[]` (empty list) | **All exceptions match.** Any exception of this type is ignored. |
| `["connection refused", "timeout"]` | The exception's `str()` representation must contain at least one of these substrings. |
| `[lambda exc: exc.status >= 500]` | The callable is invoked with the exception; a truthy return value means the exception is ignored. |
| `["connection refused", lambda exc: exc.status >= 500]` | **Strings and callables can be combined.** The exception is ignored if *any* filter matches. |

> **Note:** Empty strings in the filter list are rejected at construction time with a `TypeError`. If you need to match all messages of a given type, use an empty list `[]` instead.

### String Filters

String filters perform a substring check using Python's `in` operator:

```python
# Internal logic (simplified) for a string filter:
filter_item in str(exp)
```

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

> **Tip:** String filters are case-sensitive. `"Refused"` will not match an exception with the message `"connection refused"`. Choose your substrings carefully.

### Callable Filters

Callable filters receive the exception instance as their single argument and return a truthy value to indicate the exception should be ignored (retried). This lets you filter based on exception attributes, not just the message string.

```python
# Only retry HttpError when the status code indicates a server error
exceptions_dict = {HttpError: [lambda exc: exc.status >= 500]}

# ✅ HttpError(status=503)  → retried (callable returns True)
# ❌ HttpError(status=404)  → re-raised (callable returns False)
```

```python
# Combine a string filter with a callable filter — either can match
exceptions_dict = {HttpError: ["connection refused", lambda exc: exc.status >= 500]}

# ✅ HttpError("connection refused", status=0)   → retried (string matches)
# ✅ HttpError("server error", status=502)        → retried (callable matches)
# ❌ HttpError("not found", status=404)           → re-raised (neither matches)
```

> **Warning:** If a callable filter raises an exception itself, the error is logged as a warning and the filter is treated as non-matching. The sampler continues evaluating the remaining filters in the list.

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
   - On a type match, it retrieves the filter list and calls `_is_exception_matched(exp, filters)`.
   - If both type and filter match → return `True` (ignore the exception).
   - If the type matches but the filter does not, the sampler **continues** checking subsequent entries in the dict.
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

The sampler checks entries in iteration order. For each entry, it tests both `isinstance()` and the filter list together. If a type matches but the filter list does not pass, the sampler **continues** to the next entry in the dict. The exception is only re-raised if *no* entry matches on both type and filters.

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
    print(e.last_exp)  # The original exception (e.g., ConnectionError)
    print(e.elapsed_time)  # Seconds elapsed before the error
```

See [TimeoutExpiredError Reference](api-exceptions.html) for the full attribute and method reference.

## Quick Reference Table

| Scenario | `exceptions_dict` | Raised Exception | Result |
|---|---|---|---|
| Default — catch all | `{Exception: []}` | Any exception | Retry until timeout |
| Specific type, any message | `{ValueError: []}` | `ValueError("anything")` | Retry |
| Specific type, filtered message | `{ValueError: ["not ready"]}` | `ValueError("not ready yet")` | Retry |
| Specific type, wrong message | `{ValueError: ["not ready"]}` | `ValueError("bad input")` | Re-raise immediately |
| Callable filter match | `{HttpError: [lambda exc: exc.status >= 500]}` | `HttpError(status=503)` | Retry |
| Callable filter no match | `{HttpError: [lambda exc: exc.status >= 500]}` | `HttpError(status=404)` | Re-raise immediately |
| Mixed string + callable | `{HttpError: ["refused", lambda exc: exc.status >= 500]}` | `HttpError("refused", status=0)` | Retry (string matches) |
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
- [Using Callable Exception Filters](callable-exception-filters.html)
- [TimeoutSampler API](api-timeout-sampler.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
- [Common Polling Patterns](common-polling-patterns.html)
