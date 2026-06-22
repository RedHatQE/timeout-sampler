# @retry Decorator API

The `retry` decorator wraps a function so it is automatically polled via [`TimeoutSampler`](api-timeout-sampler.html) until it returns a truthy value or the timeout expires.

## Import

```python
from timeout_sampler import retry
```

## Signature

```python
def retry(
    wait_timeout: int,
    sleep: int,
    exceptions_dict: dict[type[Exception], list[str]] | None = None,
    print_log: bool = True,
    print_func_log: bool = True,
    print_func_args: bool = True,
) -> Callable
```

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `wait_timeout` | `int` | *(required)* | Maximum time in seconds to keep retrying the decorated function. |
| `sleep` | `int` | *(required)* | Time in seconds to wait between each call to the decorated function. |
| `exceptions_dict` | `dict[type[Exception], list[str]] \| None` | `None` | Exception filter map. When `None`, defaults to `{Exception: []}` (all exceptions ignored). See [How Exception Matching Works](exception-matching-logic.html). |
| `print_log` | `bool` | `True` | When `True`, logs elapsed time and timeout configuration. See [Controlling Log Output](controlling-logging.html). |
| `print_func_log` | `bool` | `True` | When `True`, includes function module and name in log output. |
| `print_func_args` | `bool` | `True` | When `True` (and `print_func_log` is also `True`), includes function arguments and keyword arguments in log output. |

## Parameter Mapping to TimeoutSampler

Every `@retry` parameter maps directly to a [`TimeoutSampler`](api-timeout-sampler.html) constructor parameter of the same name. The decorator also forwards the decorated function's positional arguments as `func_args` and keyword arguments as `**func_kwargs`.

| `@retry` parameter | `TimeoutSampler` parameter |
|---|---|
| `wait_timeout` | `wait_timeout` |
| `sleep` | `sleep` |
| `exceptions_dict` | `exceptions_dict` |
| `print_log` | `print_log` |
| `print_func_log` | `print_func_log` |
| `print_func_args` | `print_func_args` |
| *(decorated function)* | `func` |
| *(positional args at call time)* | `func_args` |
| *(keyword args at call time)* | `**func_kwargs` |

## Return Value

The decorator returns the first **truthy** value returned by the decorated function. If the function never returns a truthy value within `wait_timeout` seconds, a [`TimeoutExpiredError`](api-exceptions.html) is raised.

> **Note:** A return value of `False`, `None`, `0`, `""`, `[]`, `{}`, or any other falsy value is treated as a failed attempt and triggers another retry. Only truthy values cause `@retry` to stop and return.

## Exceptions

| Exception | Condition |
|---|---|
| [`TimeoutExpiredError`](api-exceptions.html) | Raised when the decorated function does not return a truthy value within `wait_timeout` seconds, or when an unmatched exception is raised by the function. |

> **Warning:** When `exceptions_dict` is `None` (the default), the internal `TimeoutSampler` uses `{Exception: []}`, which silently catches **all** exceptions during polling. Pass an explicit empty dict `{}` to let every exception propagate immediately.

## Examples

### Basic Usage

```python
from timeout_sampler import retry

@retry(wait_timeout=30, sleep=5)
def wait_for_service():
    response = requests.get("http://localhost:8080/health")
    return response.status_code == 200

# Polls every 5 seconds for up to 30 seconds.
# Returns True on success, raises TimeoutExpiredError on timeout.
wait_for_service()
```

### With Arguments

Arguments passed at call time are forwarded to the decorated function:

```python
from timeout_sampler import retry

@retry(wait_timeout=10, sleep=2)
def check_status(host, port, path="/health"):
    response = requests.get(f"http://{host}:{port}{path}")
    return response.ok

# 'host' and 'port' are forwarded as func_args;
# 'path' is forwarded as a keyword argument.
check_status("localhost", 8080, path="/ready")
```

### Filtering Specific Exceptions

```python
from timeout_sampler import retry

@retry(
    wait_timeout=20,
    sleep=3,
    exceptions_dict={ConnectionError: [], TimeoutError: ["timed out"]},
)
def fetch_data():
    return requests.get("http://api.example.com/data").json()

# ConnectionError with any message is ignored during polling.
# TimeoutError is ignored only if its message contains "timed out".
# All other exceptions propagate immediately.
result = fetch_data()
```

See [Filtering and Handling Exceptions](handling-exceptions.html) for the full exception matching semantics.

### Suppressing Log Output

```python
from timeout_sampler import retry

@retry(wait_timeout=5, sleep=1, print_log=False)
def quiet_check():
    return some_condition()
```

### Returning a Non-Boolean Truthy Value

```python
from timeout_sampler import retry

@retry(wait_timeout=15, sleep=2)
def get_items():
    items = fetch_items_from_queue()
    return items  # Returns the list when non-empty; retries on empty list

result = get_items()  # result is the first non-empty list returned
```

### Handling TimeoutExpiredError

```python
from timeout_sampler import retry, TimeoutExpiredError

@retry(wait_timeout=5, sleep=1)
def unreliable():
    return False

try:
    unreliable()
except TimeoutExpiredError as e:
    print(f"Gave up after {e.elapsed_time}s")
    print(f"Last exception: {e.last_exp}")
```

See [TimeoutExpiredError Reference](api-exceptions.html) for all available attributes on the exception.

## Related Pages

- [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html)
- [TimeoutSampler API](api-timeout-sampler.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
- [Filtering and Handling Exceptions](handling-exceptions.html)
- [How Exception Matching Works](exception-matching-logic.html)
