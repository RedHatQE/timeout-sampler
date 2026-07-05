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
    exceptions_dict: ExceptionsDict | None = None,
    print_log: bool = True,
    print_func_log: bool = True,
    print_func_args: bool = True,
    sensitive_keys: frozenset[str] | set[str] | None = None,
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
| `exceptions_dict` | `ExceptionsDict \| None` | `None` | Map of exception types to filter lists. Filters can be strings (matched as substrings of `str(exception)`) or callables (invoked with the exception instance, returning truthy to ignore). When `None`, defaults to `{Exception: []}` (all exceptions ignored). See [How Exception Matching Works](exception-matching-logic.html). |
| `print_log` | `bool` | `True` | Log elapsed time on each iteration and print a summary line at the start. |
| `print_func_log` | `bool` | `True` | Include function module and name in the startup log message. |
| `print_func_args` | `bool` | `True` | Include `func_args` and `func_kwargs` in the log when `print_func_log` is `True`. |
| `sensitive_keys` | `frozenset[str] \| set[str] \| None` | `None` | Additional keys to redact from logged kwargs (case-insensitive exact match). Merged with the built-in default sensitive keys. See [Sensitive Key Redaction](#sensitive-key-redaction). |
| `func_args` | `tuple[Any] \| None` | `None` | Positional arguments forwarded to `func`. Stored as an empty tuple when `None`. |
| `**func_kwargs` | `Any` | — | Keyword arguments forwarded to `func`. |

> **Note:** When `exceptions_dict` is omitted (or `None`), it defaults to `{Exception: []}`, which silently ignores **all** exceptions raised inside `func` until the timeout expires. Pass an explicit empty dict `{}` to re-raise every exception immediately.


> **Note:** The `exceptions_dict` is validated at construction time. Keys must be `Exception` subclasses, values must be lists, and filter items must be non-empty strings or callables. Passing invalid types (e.g., a class instead of a callable, or an empty string) raises `TypeError` immediately.

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
    ExceptionClass: ["message_substring", lambda exc: exc.attr > 0, ...],
    AnotherException: [],   # empty list = match all messages
}
```

Filter items can be **strings** (matched as substrings of `str(exception)`) or **callables** (invoked with the exception instance, returning a truthy value to ignore/retry). Both types can be combined in the same list.

| `exceptions_dict` value | Behavior |
|---|---|
| `None` (default) | Replaced internally with `{Exception: []}` — all exceptions are ignored until timeout. |
| `{}` (empty dict) | Every exception is immediately re-raised as `TimeoutExpiredError`. |
| `{ValueError: []}` | Any `ValueError` (or subclass) is ignored regardless of message text. |
| `{ValueError: ["connection"]}` | `ValueError` is ignored only if `"connection"` appears in `str(exp)`. |
| `{HttpError: [lambda exc: exc.status >= 500]}` | `HttpError` is ignored only if the callable returns truthy. |
| `{HttpError: ["connection refused", lambda exc: exc.status >= 500]}` | `HttpError` is ignored if **either** the string matches **or** the callable returns truthy. |
| `{KeyError: ["x"], IndexError: ["y"]}` | Multiple exception types, each with independent filters. |

> **Tip:** The match uses `isinstance()`, so a parent class in `exceptions_dict` will also catch child classes. See [How Exception Matching Works](exception-matching-logic.html) for inheritance examples.


> **Warning:** If a callable filter raises an exception itself (e.g., accessing a missing attribute), it is logged as a warning and treated as non-matching — it will **not** propagate.

### Exception Handling Outcomes

| Scenario | Result |
|---|---|
| Exception class (or parent) is in `exceptions_dict` and a filter matches (string substring, callable returns truthy, or filter list is empty) | Exception is **ignored**; sampler sleeps and retries. |
| Exception class is in `exceptions_dict` but **no** filter matches | `TimeoutExpiredError` is raised **immediately**. |
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

### Example — Callable Filter

```python
from timeout_sampler import TimeoutSampler

# Only retry on HTTP 5xx errors; 4xx errors raise immediately.
for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=make_request,
    exceptions_dict={HttpError: [lambda exc: exc.status >= 500]},
):
    if sample:
        break
```

### Example — Mixed String and Callable Filters

```python
from timeout_sampler import TimeoutSampler

# Retry if message contains "connection refused" OR status >= 500.
for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=make_request,
    exceptions_dict={HttpError: ["connection refused", lambda exc: exc.status >= 500]},
):
    if sample:
        break
```

---

## Internal Methods

These methods are not part of the public API but are documented for contributor reference.

### `_validate_exceptions_dict`

```python
@staticmethod
_validate_exceptions_dict(exceptions_dict: ExceptionsDict) -> ExceptionsDict
```

Validates and returns a defensive copy of `exceptions_dict`. Called during `__init__`.

**Raises:** `TypeError` if keys aren't `Exception` subclasses, values aren't lists, or filter items aren't non-empty strings or callables. Passing a class (e.g., `ValueError`) as a filter item instead of a callable also raises `TypeError`.

### `_is_exception_matched`

```python
@staticmethod
_is_exception_matched(exp: Exception, exception_filters: list[ExceptionFilter]) -> bool
```

| Parameter | Type | Description |
|---|---|---|
| `exp` | `Exception` | The exception instance raised by `func`. |
| `exception_filters` | `list[ExceptionFilter]` | List of allowed filters — strings (substring match against `str(exp)`) or callables (invoked with `exp`, returning truthy to match). Empty list matches everything. |

**Returns:** `True` if `exception_filters` is empty, if any string in the list is a substring of `str(exp)`, or if any callable returns a truthy value when called with `exp`. `False` otherwise.

> **Note:** If a callable filter raises an exception when invoked, a warning is logged and the filter is treated as non-matching.

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

### `_redact`

```python
_redact(self, data: Any, _depth: int = 0) -> Any
```

Recursively redacts values whose keys exactly match sensitive keys (case-insensitive). Traverses dicts, lists, and tuples up to `_MAX_REDACT_DEPTH` (20) levels. Values for matching keys are replaced with `"***"`.

### `_func_log` (cached property)

```python
@functools.cached_property
_func_log(self) -> str
```

**Returns:** A formatted string describing the function call, e.g. `"Function: mymodule.my_func Args: (1, 2) Kwargs: {'key': 'val'}"`. Controlled by `print_func_log` and `print_func_args`. Sensitive values in args and kwargs are redacted.

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

## Sensitive Key Redaction

When logging function arguments, `TimeoutSampler` automatically redacts values for keys that match known sensitive names. Matching is **case-insensitive** and **exact** (e.g., `"token"` matches a key named `"Token"` or `"TOKEN"` but **not** `"nextPageToken"`).

### Default Sensitive Keys

`authorization`, `token`, `access_token`, `password`, `secret`, `api_key`, `apikey`

### Adding Custom Keys

Pass the `sensitive_keys` parameter to merge additional keys with the defaults:

```python
for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=call_api,
    sensitive_keys=frozenset({"x-custom-secret"}),
    headers={"Authorization": "Bearer token", "x-custom-secret": "value"}, # pragma: allowlist secret
):
    if sample:
        break
# Log output: Kwargs: {'headers': {'Authorization': '***', 'x-custom-secret': '***'}}
```

Redaction traverses dicts, lists, and tuples recursively up to 20 levels deep. Data nested beyond this limit is replaced with `"<redacted: max depth exceeded>"`.

> **Note:** Passing an empty `frozenset()` as `sensitive_keys` still uses all default sensitive keys. To redact **only** defaults, omit the parameter entirely.


> **Warning:** All elements of `sensitive_keys` must be strings. Passing non-string elements (e.g., `int`, `None`) raises `TypeError` at construction time.

---

## Logging Behavior

Logging is emitted via `simple_logger` at `INFO` level.

| Flag | Default | Effect when `True` |
|---|---|---|
| `print_log` | `True` | Logs a startup message with wait/sleep times and logs elapsed time after each iteration where `func` raises an exception or after yield. |
| `print_func_log` | `True` | Appends function module and name to the startup log message. Requires `print_log=True`. |
| `print_func_args` | `True` | Includes `Args` and `Kwargs` in the function log (with sensitive values redacted). Requires `print_func_log=True`. |

See [Controlling Log Output](controlling-logging.html) for usage examples and sample output.

---

## Import Path

```python
from timeout_sampler import TimeoutSampler
```

The class is exported from the top-level `timeout_sampler` package (`timeout_sampler/__init__.py`).

---

## Type Aliases

The following public type aliases are used in the `TimeoutSampler` API and are re-exported from the `timeout_sampler` package:

```python
from timeout_sampler import ExceptionFilter, ExceptionsDict
```

| Alias | Definition | Description |
|---|---|---|
| `ExceptionFilter` | `str \| Callable[[Exception], bool]` | A single filter item — either a substring to match against `str(exception)` or a callable that receives the exception and returns truthy to ignore. |
| `ExceptionsDict` | `dict[type[Exception], list[ExceptionFilter]]` | Mapping of exception classes to their filter lists. Used as the type for the `exceptions_dict` parameter. |

## Related Pages

- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [How Exception Matching Works](exception-matching-logic.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
- [Controlling Log Output](controlling-logging.html)
- [@retry Decorator API](api-retry-decorator.html)
