# TimeoutSampler API

Complete reference for the `TimeoutSampler` class — constructor parameters, iteration protocol, exception handling, and return semantics.

```python
from timeout_sampler import TimeoutSampler
```

## Constructor

```python
TimeoutSampler(
    wait_timeout: float,
    sleep: int,
    func: Callable,
    exceptions_dict: dict[type[Exception], list[str]] | None = None,
    print_log: bool = True,
    print_func_log: bool = True,
    print_func_args: bool = True,
    func_args: tuple[Any] | None = None,
    **func_kwargs: Any,
)
```

### Parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `wait_timeout` | `float` | *(required)* | Maximum time in seconds to poll `func` before raising `TimeoutExpiredError`. |
| `sleep` | `int` | *(required)* | Time in seconds to sleep between successive calls to `func`. |
| `func` | `Callable` | *(required)* | The function to poll. Called as `func(*func_args, **func_kwargs)` on each iteration. |
| `exceptions_dict` | `dict[type[Exception], list[str]] \| None` | `None` | Map of exception types to message-filter lists. When `None`, defaults to `{Exception: []}` (all exceptions ignored). See [How Exception Matching Works](exception-matching-logic.html). |
| `print_log` | `bool` | `True` | Log elapsed time on each iteration and print a summary line at the start. |
| `print_func_log` | `bool` | `True` | Include function module and name in the startup log message. |
| `print_func_args` | `bool` | `True` | Include `func_args` and `func_kwargs` in the log when `print_func_log` is `True`. |
| `func_args` | `tuple[Any] \| None` | `None` | Positional arguments forwarded to `func`. Stored as an empty tuple when `None`. |
| `**func_kwargs` | `Any` | — | Keyword arguments forwarded to `func`. |

> **Note:** When `exceptions_dict` is omitted (or `None`), it defaults to `{Exception: []}`, which silently ignores **all** exceptions raised inside `func` until the timeout expires. Pass an explicit empty dict `{}` to re-raise every exception immediately.

### Example — Basic Construction

```python
from timeout_sampler import TimeoutSampler

def check_service():
    return {"status": "ready"}

sampler = TimeoutSampler(
    wait_timeout=30,
    sleep=5,
    func=check_service,
)
```

### Example — Passing Arguments to `func`

```python
import requests
from timeout_sampler import TimeoutSampler

sampler = TimeoutSampler(
    wait_timeout=60,
    sleep=2,
    func=requests.get,
    func_args=("https://api.example.com/health",),
    timeout=5,          # forwarded as requests.get(..., timeout=5)
)
```

---

## Iteration Protocol

`TimeoutSampler` implements `__iter__`. Use it in a `for` loop. Each iteration calls `func(*func_args, **func_kwargs)` and yields the return value.

```python
def __iter__(self) -> Any
```

**Yields:** The return value of `func` on each successful call.

**Raises:** [`TimeoutExpiredError`](api-exceptions.html) when the elapsed time exceeds `wait_timeout`.

### Iteration Lifecycle

1. A `TimeoutWatch` is created with `timeout=wait_timeout`.
2. While remaining time > 0:
   - `func(*func_args, **func_kwargs)` is called.
   - The return value is **yielded** to the caller.
   - After the caller processes the yielded value and continues the loop, the sampler sleeps for `sleep` seconds.
3. If the loop exhausts the timeout without the caller breaking out, `TimeoutExpiredError` is raised.

> **Warning:** `TimeoutSampler` does **not** evaluate the return value of `func`. The caller must inspect each yielded sample and `break` or `return` when a satisfactory value is found. Failing to break out of the loop will always result in `TimeoutExpiredError`.

### Example — Iterate Until Success

```python
from timeout_sampler import TimeoutSampler

def get_pod_status():
    # returns "Pending", "Running", etc.
    ...

for sample in TimeoutSampler(wait_timeout=120, sleep=5, func=get_pod_status):
    if sample == "Running":
        break
```

### Example — Iterate with Logging Disabled

```python
for sample in TimeoutSampler(
    wait_timeout=10,
    sleep=1,
    func=lambda: True,
    print_log=False,
):
    if sample:
        break
```

---

## Exception Handling During Iteration

When `func` raises an exception during iteration, `TimeoutSampler` checks it against `exceptions_dict` using `_should_ignore_exception` and `_is_exception_matched`.

For a detailed walkthrough of the matching algorithm, see [How Exception Matching Works](exception-matching-logic.html).

### `exceptions_dict` Format

```python
{
    ExceptionClass: [message_substring_1, message_substring_2, ...],
    AnotherException: [],   # empty list = match all messages
}
```

| `exceptions_dict` value | Behavior |
|---|---|
| `None` (default) | Replaced internally with `{Exception: []}` — all exceptions are ignored until timeout. |
| `{}` (empty dict) | Every exception is immediately re-raised as `TimeoutExpiredError`. |
| `{ValueError: []}` | Any `ValueError` (or subclass) is ignored regardless of message text. |
| `{ValueError: ["connection"]}` | `ValueError` is ignored only if `"connection"` appears in `str(exp)`. |
| `{KeyError: ["x"], IndexError: ["y"]}` | Multiple exception types, each with independent message filters. |

> **Tip:** The match uses `isinstance()`, so a parent class in `exceptions_dict` will also catch child classes. See [How Exception Matching Works](exception-matching-logic.html) for inheritance examples.

### Exception Handling Outcomes

| Scenario | Result |
|---|---|
| Exception class (or parent) is in `exceptions_dict` and message matches (or filter list is empty) | Exception is **ignored**; sampler sleeps and retries. |
| Exception class is in `exceptions_dict` but message does **not** match any filter string | `TimeoutExpiredError` is raised **immediately**. |
| Exception class is **not** in `exceptions_dict` (and no parent class is listed) | `TimeoutExpiredError` is raised **immediately**. |
| No exception; timeout expires | `TimeoutExpiredError` is raised after the loop ends. |

### Example — Ignore Specific Exceptions

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=2,
    func=my_flaky_func,
    exceptions_dict={ConnectionError: [], TimeoutError: []},
):
    if sample:
        break
```

### Example — Filter by Exception Message

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=2,
    func=my_func,
    exceptions_dict={ValueError: ["not ready", "try again"]},
):
    if sample:
        break
```

A `ValueError("resource not ready")` is ignored (contains `"not ready"`). A `ValueError("invalid input")` causes an immediate `TimeoutExpiredError`.

---

## Internal Methods

These methods are not part of the public API but are documented for contributor reference.

### `_is_exception_matched`

```python
@staticmethod
_is_exception_matched(exp: Exception, exception_messages: list[str]) -> bool
```

| Parameter | Type | Description |
|---|---|---|
| `exp` | `Exception` | The exception instance raised by `func`. |
| `exception_messages` | `list[str]` | List of allowed substrings. Empty list matches everything. |

**Returns:** `True` if `exception_messages` is empty, or if any non-empty string in the list is a substring of `str(exp)`. `False` otherwise.

> **Note:** Empty strings in the message list are explicitly skipped — they will not produce a match.

### `_should_ignore_exception`

```python
_should_ignore_exception(self, exp: Exception) -> bool
```

| Parameter | Type | Description |
|---|---|---|
| `exp` | `Exception` | The exception instance raised by `func`. |

**Returns:** `True` if the exception should be **ignored** (matches an entry in `exceptions_dict` via `isinstance()` and message filtering). `False` if the exception should be re-raised.

### `_get_func_info`

```python
_get_func_info(self, _func: Callable, type_: str) -> Any
```

Resolves function metadata (`__module__`, `__name__`) for regular, `partial`, and `lambda` functions. Used internally to build log messages.

### `_func_log` (property)

```python
@property
_func_log(self) -> str
```

**Returns:** A formatted string describing the function call, e.g. `"Function: mymodule.my_func Args: (1, 2) Kwargs: {'key': 'val'}"`. Controlled by `print_func_log` and `print_func_args`.

### `_get_exception_log`

```python
_get_exception_log(self, exp: Exception | None = None) -> str
```

| Parameter | Type | Description |
|---|---|---|
| `exp` | `Exception \| None` | The last exception raised, or `None` if no exception occurred. |

**Returns:** A multi-line string containing the timeout value, function info (if `print_func_log` is `True`), and the last exception class name and message. This string becomes the `value` attribute of the raised `TimeoutExpiredError`.

---

## Raised Exceptions

`TimeoutSampler` raises only one exception type: [`TimeoutExpiredError`](api-exceptions.html).

| Condition | `last_exp` | `elapsed_time` |
|---|---|---|
| Timeout expires with no exception from `func` | `None` | `None` |
| Timeout expires after ignored exceptions | Last ignored `Exception` instance | `None` |
| Exception not matched by `exceptions_dict` | The unmatched `Exception` instance | Seconds elapsed at time of exception |

See [TimeoutExpiredError Reference](api-exceptions.html) for the full attribute and string-representation reference.

---

## Logging Behavior

Logging is emitted via `simple_logger` at `INFO` level.

| Flag | Default | Effect when `True` |
|---|---|---|
| `print_log` | `True` | Logs a startup message with wait/sleep times and logs elapsed time after each iteration where `func` raises an exception or after yield. |
| `print_func_log` | `True` | Appends function module and name to the startup log message. Requires `print_log=True`. |
| `print_func_args` | `True` | Includes `Args` and `Kwargs` in the function log. Requires `print_func_log=True`. |

See [Controlling Log Output](controlling-logging.html) for usage examples and sample output.

---

## Import Path

```python
from timeout_sampler import TimeoutSampler
```

The class is exported from the top-level `timeout_sampler` package (`timeout_sampler/__init__.py`).

## Related Pages

- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
- [How Exception Matching Works](exception-matching-logic.html)
- [Controlling Log Output](controlling-logging.html)
- [TimeoutWatch API](api-timeout-watch.html)
