# Using Callable Exception Filters

Filter exceptions during polling based on runtime attributes — like HTTP status codes or error categories — by passing callable filters (lambdas or functions) alongside string filters in your `exceptions_dict`.

## Prerequisites

- `timeout-sampler` installed in your project (see [Getting Started with timeout-sampler](quickstart.html))
- Basic familiarity with `exceptions_dict` string-based filtering (see [Filtering and Handling Exceptions](handling-exceptions.html))

## Quick Example

Ignore server errors (status ≥ 500) and retry, but immediately stop on client errors:

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=2,
    func=call_my_api,
    exceptions_dict={
        HttpError: [lambda exc: exc.status >= 500]
    },
):
    if sample:
        break
```

If `call_my_api` raises an `HttpError` with `status=502`, the sampler retries. If it raises one with `status=404`, polling stops immediately with a `TimeoutExpiredError`.

## Type Aliases

The library exports two type aliases you can use for type-safe exception filter configuration:

```python
from timeout_sampler import ExceptionFilter, ExceptionsDict
```

| Type Alias        | Definition                                        | Purpose                                                   |
|-------------------|---------------------------------------------------|-----------------------------------------------------------|
| `ExceptionFilter` | `str \| Callable[[Exception], bool]`              | A single filter: either a substring match or a callable   |
| `ExceptionsDict`  | `dict[type[Exception], list[ExceptionFilter]]`    | The full mapping passed to `exceptions_dict`              |

Use these to annotate your own helper functions or configuration builders:

```python
from timeout_sampler import ExceptionsDict

def build_api_filters(retryable_codes: list[int]) -> ExceptionsDict:
    return {
        HttpError: [lambda exc: exc.status in retryable_codes]
    }

filters = build_api_filters([500, 502, 503, 504])
```

## How Callable Filters Work

1. Your polled function raises an exception.
2. The sampler checks if the exception's type (or a parent type) is a key in `exceptions_dict`.
3. If the filter list is **empty** (`[]`), all instances of that exception are ignored and the sampler retries.
4. If the filter list contains **callables**, each callable is invoked with the exception instance. If any callable returns a **truthy** value, the exception is ignored and the sampler retries.
5. If no filter matches, polling stops and a `TimeoutExpiredError` is raised.

> **Note:** Filters are evaluated in list order. The sampler stops at the first match — either a string substring match or a callable returning truthy.

## Writing Callable Filters

A callable filter is any function or lambda that:

- Accepts exactly **one argument**: the exception instance
- Returns a **truthy** value to ignore the exception (retry), or **falsy** to stop

### Lambda filters

The most concise option for simple conditions:

```python
exceptions_dict = {
    HttpError: [lambda exc: exc.status >= 500]
}
```

### Named functions

Better for complex logic or reusability:

```python
def is_retryable_error(exc):
    """Retry on server errors and rate limiting."""
    return exc.status >= 500 or exc.status == 429

exceptions_dict = {
    HttpError: [is_retryable_error]
}
```

### Filtering on exception attributes

Callable filters shine when you need to inspect attributes beyond the exception message:

```python
# Retry only on specific error codes
exceptions_dict = {
    DatabaseError: [lambda exc: exc.error_code in ("LOCK_TIMEOUT", "DEADLOCK")]
}

# Retry when a response header says to
exceptions_dict = {
    ApiError: [lambda exc: exc.retry_after is not None]
}
```

## Combining String and Callable Filters

You can mix string and callable filters in the same list. The sampler checks each filter in order and retries on the **first match**:

```python
exceptions_dict = {
    ConnectionError: [
        "Connection refused",                    # string: match against str(exception)
        lambda exc: getattr(exc, "errno", 0) == 104,  # callable: check attribute
    ]
}
```

| Filter type | How it matches                                                    |
|-------------|-------------------------------------------------------------------|
| String      | Checked as a **substring** of `str(exception)`                    |
| Callable    | Called with the exception instance; retries if return is **truthy**|

> **Tip:** Put the most common match first in the list to short-circuit evaluation.

## Using Callable Filters with the `@retry` Decorator

Callable filters work identically with the `@retry` decorator:

```python
from timeout_sampler import retry

@retry(
    wait_timeout=60,
    sleep=5,
    exceptions_dict={
        HttpError: [lambda exc: exc.status >= 500],
        ConnectionError: [],
    },
)
def fetch_data(url):
    return requests.get(url).json()
```

See [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html) for full decorator usage.

## Advanced Usage

### Multiple exception types with different filters

Map different exception classes to different filter strategies in a single `exceptions_dict`:

```python
exceptions_dict = {
    HttpError: [lambda exc: exc.status >= 500],
    ConnectionError: [],                        # retry all connection errors
    TimeoutError: ["read timed out"],           # retry only read timeouts
}
```

### Callable filters with `functools.partial`

Use `functools.partial` to create reusable parameterized filters:

```python
from functools import partial

def status_in_range(exc, low, high):
    return low <= exc.status < high

exceptions_dict = {
    HttpError: [partial(status_in_range, low=500, high=600)]
}
```

### Accessing `last_exp` after timeout

When polling ultimately times out, the `TimeoutExpiredError` carries the last exception on its `last_exp` attribute, so you can inspect which exception caused the final failure:

```python
try:
    for sample in TimeoutSampler(
        wait_timeout=10,
        sleep=2,
        func=call_my_api,
        exceptions_dict={HttpError: [lambda exc: exc.status >= 500]},
    ):
        if sample:
            break
except TimeoutExpiredError as e:
    if e.last_exp:
        print(f"Last error status: {e.last_exp.status}")
```

See [TimeoutExpiredError Reference](api-exceptions.html) for all available attributes.

## Error Handling When a Callable Filter Raises

If your callable filter itself raises an exception (for example, accessing an attribute that doesn't exist), the sampler handles it **safely**:

- The failing filter is **skipped** and treated as non-matching.
- A warning is logged: `Callable filter <filter> raised <error> for <ExceptionType>, treating as non-matching`.
- Evaluation continues with the remaining filters in the list.
- If no other filter matches, the exception is **not ignored** and a `TimeoutExpiredError` is raised.

```python
# This filter accesses .status, but the exception might not have that attribute
exceptions_dict = {
    Exception: [lambda exc: exc.status >= 500]
}
```

If a plain `Exception("something broke")` is raised (no `.status` attribute), the callable filter raises `AttributeError` internally. The sampler logs a warning, skips that filter, and since no filter matched, stops polling immediately.

> **Warning:** The sampler will never propagate an exception raised by a filter callable. It always catches the error, logs it, and moves on. Make sure your filter logic is correct — a broken filter silently becomes a non-match.

## Validation at Initialization

The `exceptions_dict` is validated when you create a `TimeoutSampler` or apply `@retry` — not at polling time. Invalid configurations raise `TypeError` immediately:

| Mistake                              | Error message                                                  |
|--------------------------------------|----------------------------------------------------------------|
| Using a class as a filter item       | `contains a class (ClassName) instead of a callable or string` |
| Using an empty string as a filter    | `contains an empty string`                                     |
| Using a non-callable, non-string     | `expected str or callable`                                     |
| Using a non-Exception class as a key | `must be an Exception subclass`                                |

```python
# ❌ Wrong: passing an exception class as a filter
exceptions_dict = {HttpError: [ValueError]}
# TypeError: contains a class (ValueError) instead of a callable or string.
# Use a lambda (e.g., lambda exc: exc.status >= 500) instead.

# ✅ Right: passing a callable
exceptions_dict = {HttpError: [lambda exc: isinstance(exc.__cause__, ValueError)]}
```

> **Tip:** Early validation means you'll catch configuration mistakes in tests, not in production during a retry loop.

## Troubleshooting

**Filter never matches even though it should**
- Verify the callable receives the correct exception type. Use `type(exc)` in a test filter to confirm.
- Check that your callable returns a **truthy** value (not `None`). A filter that doesn't explicitly `return True` returns `None`, which is falsy.

**Filter always matches when it shouldn't**
- Ensure your callable isn't returning a truthy value by accident. For example, `lambda exc: exc.message` returns the message string, which is truthy for any non-empty message.

**"Callable filter raised..." warning in logs**
- Your filter callable is crashing at runtime. Check for attribute access on exception types that don't have the expected attribute. Use `getattr(exc, "attr", default)` for defensive access.

## Related Pages

- [How Exception Matching Works](exception-matching-logic.html)
- [Filtering and Handling Exceptions](handling-exceptions.html)
- [TimeoutSampler API](api-timeout-sampler.html)
- [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
