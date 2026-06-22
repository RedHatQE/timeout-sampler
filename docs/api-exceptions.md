# TimeoutExpiredError Reference

`TimeoutExpiredError` is the exception raised by [`TimeoutSampler`](api-timeout-sampler.html) and the [`@retry` decorator](api-retry-decorator.html) when the polled function does not produce a truthy result within the specified timeout, or when a raised exception is not matched by the configured `exceptions_dict`.

## Import

```python
from timeout_sampler import TimeoutExpiredError
```

## Class Signature

```python
class TimeoutExpiredError(Exception):
    def __init__(
        self,
        value: str,
        last_exp: Exception | None = None,
        elapsed_time: float | None = None,
    ) -> None: ...
```

`TimeoutExpiredError` is a direct subclass of `Exception`.

## Constructor Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `value` | `str` | *(required)* | Message describing the timeout context. Includes timeout duration, function info, and the last exception name/text. |
| `last_exp` | `Exception \| None` | `None` | The last exception caught during polling, if any. `None` when the function returned without raising but never produced a truthy result. |
| `elapsed_time` | `float \| None` | `None` | Seconds elapsed from the start of polling until the error was raised. `None` when not tracked (e.g., on a natural timeout expiry at the end of the iteration loop). |

## Instance Attributes

| Attribute | Type | Description |
|---|---|---|
| `value` | `str` | The descriptive message passed to the constructor. |
| `last_exp` | `Exception \| None` | Reference to the last exception raised by the polled function. Useful for inspecting the root cause of a timeout. |
| `elapsed_time` | `float \| None` | Wall-clock seconds elapsed since polling started. Present when the timeout was triggered mid-iteration; `None` when the timeout watch expired naturally at the loop boundary. |

### Accessing `last_exp`

```python
from timeout_sampler import TimeoutSampler, TimeoutExpiredError

try:
    for sample in TimeoutSampler(
        wait_timeout=5,
        sleep=1,
        func=my_flaky_function,
        exceptions_dict={ConnectionError: []},
    ):
        if sample:
            break
except TimeoutExpiredError as exp:
    if exp.last_exp is not None:
        print(f"Root cause: {type(exp.last_exp).__name__}: {exp.last_exp}")
    else:
        print("Function never raised, but never returned truthy either")
```

### Accessing `elapsed_time`

```python
from timeout_sampler import TimeoutSampler, TimeoutExpiredError

try:
    for sample in TimeoutSampler(
        wait_timeout=30,
        sleep=2,
        func=check_service_health,
    ):
        if sample:
            break
except TimeoutExpiredError as exp:
    if exp.elapsed_time is not None:
        print(f"Failed after {exp.elapsed_time:.2f} seconds")
```

## String Representation (`__str__`)

`str(exp)` returns a formatted message. The format depends on whether `elapsed_time` is set.

**Without `elapsed_time`:**

```
Timed Out: <value>.
```

**With `elapsed_time`:**

```
Timed Out: <value>.
Elapsed time: <seconds> [<H:MM:SS>]
```

The elapsed-time line uses `datetime.timedelta` for the human-readable duration.

### Example Output

```python
from timeout_sampler import TimeoutExpiredError

# Minimal
err = TimeoutExpiredError(value="10")
print(str(err))
# Timed Out: 10.

# With elapsed time
err = TimeoutExpiredError(value="10", elapsed_time=7.53)
print(str(err))
# Timed Out: 10.
# Elapsed time: 7.53 [0:00:07.530000]
```

> **Note:** When `TimeoutExpiredError` is raised by `TimeoutSampler`, the `value` string contains multiple lines with the timeout duration, function info, and last exception details. The exact format is an internal detail of `TimeoutSampler._get_exception_log()`. See [TimeoutSampler API](api-timeout-sampler.html) for iteration behavior.

### Realistic `str()` from `TimeoutSampler`

When `TimeoutSampler` raises `TimeoutExpiredError`, the string representation typically looks like:

```
Timed Out: 5
Function: my_module.check_service_health
Last exception: ConnectionError: connection refused.
Elapsed time: 4.02 [0:00:04.020000]
```

## When `elapsed_time` Is Set vs. `None`

| Scenario | `elapsed_time` | `last_exp` |
|---|---|---|
| Exception raised mid-iteration that is **not** matched by `exceptions_dict` | Set (seconds since start) | The unmatched exception |
| Matched exception keeps being raised until timeout expires naturally | `None` | The last matched exception |
| Function returns a non-truthy value until timeout expires naturally | `None` | `None` |

> **Tip:** To guarantee `elapsed_time` is always available in your error handling, check for `None` before using it in arithmetic or formatting.

## Catching `TimeoutExpiredError`

`TimeoutExpiredError` can be caught as itself or as its parent `Exception`:

```python
from timeout_sampler import TimeoutExpiredError

# Specific catch
try:
    for sample in sampler:
        if sample:
            break
except TimeoutExpiredError:
    print("Polling timed out")

# Broader catch (also works)
try:
    for sample in sampler:
        if sample:
            break
except Exception as e:
    if isinstance(e, TimeoutExpiredError):
        print(f"Timeout with last_exp={e.last_exp}")
```

## Constructing Manually

You can construct `TimeoutExpiredError` directly for testing or custom polling logic:

```python
from timeout_sampler import TimeoutExpiredError

# Simulate a timeout with a root cause
root_cause = ConnectionError("connection refused")
err = TimeoutExpiredError(
    value="30",
    last_exp=root_cause,
    elapsed_time=29.87,
)

assert err.value == "30"
assert err.last_exp is root_cause
assert err.elapsed_time == 29.87
assert "Timed Out: 30." in str(err)
assert "Elapsed time: 29.87" in str(err)
```

## Related Pages

- [TimeoutSampler API](api-timeout-sampler.html) — constructor parameters and iteration behavior that produce `TimeoutExpiredError`
- [@retry Decorator API](api-retry-decorator.html) — decorator that raises `TimeoutExpiredError` on timeout
- [Filtering and Handling Exceptions](handling-exceptions.html) — configuring `exceptions_dict` to control which exceptions trigger an immediate `TimeoutExpiredError` vs. being silently retried
- [How Exception Matching Works](exception-matching-logic.html) — the algorithm that determines whether an exception is matched or causes `TimeoutExpiredError`

## Related Pages

- [Filtering and Handling Exceptions](handling-exceptions.html)
- [TimeoutSampler API](api-timeout-sampler.html)
- [@retry Decorator API](api-retry-decorator.html)
- [How Exception Matching Works](exception-matching-logic.html)
- [Tracking Elapsed Time with TimeoutWatch](tracking-elapsed-time.html)
