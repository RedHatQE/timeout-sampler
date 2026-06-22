# Controlling Log Output

When debugging polling loops or running in production, you may want to control how much logging `timeout-sampler` produces. Three boolean parameters — `print_log`, `print_func_log`, and `print_func_args` — let you toggle elapsed-time messages, function-call details, and argument visibility independently.

## Prerequisites

- `timeout-sampler` installed in your project (see [Getting Started with timeout-sampler](quickstart.html))
- Basic familiarity with `TimeoutSampler` or the `@retry` decorator

## Quick Example

Suppress all log output by setting `print_log=False`:

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=5,
    func=my_check,
    print_log=False,
):
    if sample:
        break
```

No log lines are emitted — no elapsed time, no function info, nothing.

## Understanding the Three Parameters

All three parameters default to `True`. Here's what each one controls:

| Parameter | Default | What it controls |
|---|---|---|
| `print_log` | `True` | Master switch — controls whether *any* log output is emitted |
| `print_func_log` | `True` | Adds the function name and module to the log line |
| `print_func_args` | `True` | Includes positional and keyword arguments in the function log |

> **Note:** `print_func_log` and `print_func_args` only take effect when `print_log` is `True`. Setting `print_log=False` silences everything regardless of the other two settings.

## Step-by-Step: Choosing a Logging Level

### 1. Full logging (default)

```python
sampler = TimeoutSampler(
    wait_timeout=60,
    sleep=5,
    func=check_service,
    func_args=("https://api.example.com",),
    retries=3,
)
```

Log output:

```
Waiting for 60 seconds [0:01:00], retry every 5 seconds. (Function: myapp.health.check_service Args: ('https://api.example.com',) Kwargs: {'retries': 3})
Elapsed time: 5.002 [0:00:05.002000]
```

### 2. Hide arguments only

When function arguments contain secrets or are too verbose:

```python
sampler = TimeoutSampler(
    wait_timeout=60,
    sleep=5,
    func=check_service,
    print_func_args=False,
    func_args=("https://api.example.com",),
    token="s3cret",
)
```

Log output:

```
Waiting for 60 seconds [0:01:00], retry every 5 seconds. (Function: myapp.health.check_service)
Elapsed time: 5.002 [0:00:05.002000]
```

The function name and module are still logged, but `Args` and `Kwargs` are omitted.

### 3. Hide function details entirely

When you only care about timing:

```python
sampler = TimeoutSampler(
    wait_timeout=60,
    sleep=5,
    func=check_service,
    print_func_log=False,
)
```

Log output:

```
Waiting for 60 seconds [0:01:00], retry every 5 seconds.
Elapsed time: 5.002 [0:00:05.002000]
```

> **Tip:** Setting `print_func_log=False` also suppresses argument output, so you don't need to set `print_func_args=False` separately.

### 4. Silence all logging

For production code, test suites, or inner loops where log noise is unwanted:

```python
sampler = TimeoutSampler(
    wait_timeout=60,
    sleep=5,
    func=check_service,
    print_log=False,
)
```

No log output is produced at all — neither the initial "Waiting for…" message nor the per-iteration elapsed-time lines.

## Using with the @retry Decorator

The same three parameters are available on the `@retry` decorator:

```python
from timeout_sampler import retry

@retry(wait_timeout=30, sleep=5, print_log=True, print_func_log=True, print_func_args=False)
def fetch_data(api_key):
    response = requests.get("https://api.example.com", headers={"Authorization": api_key})
    return response.ok
```

This logs the function name and elapsed time but omits the `api_key` argument from log output.

See [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html) for full decorator usage.

## Parameter Combination Reference

| `print_log` | `print_func_log` | `print_func_args` | "Waiting for…" line | Function name in log | Args/Kwargs in log | Elapsed time lines |
|---|---|---|---|---|---|---|
| `True`  | `True`  | `True`  | ✅ | ✅ | ✅ | ✅ |
| `True`  | `True`  | `False` | ✅ | ✅ | ❌ | ✅ |
| `True`  | `False` | `True`  | ✅ | ❌ | ❌ | ✅ |
| `True`  | `False` | `False` | ✅ | ❌ | ❌ | ✅ |
| `False` | `True`  | `True`  | ❌ | ❌ | ❌ | ❌ |
| `False` | `True`  | `False` | ❌ | ❌ | ❌ | ❌ |
| `False` | `False` | `True`  | ❌ | ❌ | ❌ | ❌ |
| `False` | `False` | `False` | ❌ | ❌ | ❌ | ❌ |

> **Note:** When `print_func_log` is `False`, arguments are never shown — even if `print_func_args` is `True` — because the entire function info block is omitted.

## Advanced Usage

### Logging in Exception Scenarios

The `print_func_log` parameter also affects the error message inside `TimeoutExpiredError`. When a timeout expires:

- If `print_func_log=True`, the exception message includes the function name, module, and (if `print_func_args=True`) arguments.
- If `print_func_log=False`, the function info line in the exception message is empty.

```python
from timeout_sampler import TimeoutSampler, TimeoutExpiredError

try:
    for sample in TimeoutSampler(
        wait_timeout=5,
        sleep=1,
        func=my_check,
        print_func_log=True,
    ):
        if sample:
            break
except TimeoutExpiredError as e:
    # str(e) includes: "Function: mymodule.my_check"
    print(e)
```

See [TimeoutExpiredError Reference](api-exceptions.html) for details on exception attributes.

### Logging with Lambda and Partial Functions

`timeout-sampler` resolves function names through `functools.partial` wrappers and lambda expressions. When `print_func_log=True`, it follows partial chains to find the underlying function and displays lambda details including free variables and referenced names.

```python
from functools import partial

check = partial(requests.get, "https://example.com")

for sample in TimeoutSampler(
    wait_timeout=10,
    sleep=2,
    func=check,
    print_func_log=True,
    print_func_args=True,
):
    if sample.ok:
        break
```

The log will show the resolved underlying function name rather than `functools.partial`.

### Selective Logging in Test Suites

When writing tests, suppress logging to keep test output clean:

```python
@retry(wait_timeout=5, sleep=1, print_log=False)
def wait_for_ready():
    return service.is_ready()
```

> **Tip:** The test suite for `timeout-sampler` itself uses `print_log=False` throughout to avoid noisy output during test runs.

## Troubleshooting

**Logs appear even though I set `print_func_log=False`**
The elapsed-time lines are controlled by `print_log`, not `print_func_log`. Set `print_log=False` to suppress all output, or leave `print_log=True` to keep only the timing information.

**Arguments still appear in `TimeoutExpiredError` messages**
The `print_func_args` parameter controls argument visibility in both the log output *and* the exception message. Verify that `print_func_args=False` is set on the `TimeoutSampler` or `@retry` call that raises the error.

**I want to customize the logger itself**
`timeout-sampler` uses `python-simple-logger` for its logging backend. The log parameters described on this page control *what* is logged, not *where* or *how*. To configure log levels, formats, or destinations, refer to `python-simple-logger` documentation.

## Related Pages

- [TimeoutSampler API](api-timeout-sampler.html)
- [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html)
- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [@retry Decorator API](api-retry-decorator.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
