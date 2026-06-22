# Polling a Function with TimeoutSampler

Poll any callable at regular intervals, inspect each return value, and break out as soon as a success condition is met — all with a built-in timeout safety net.

## Prerequisites

- `timeout-sampler` installed in your project (see [Getting Started with timeout-sampler](quickstart.html))

## Quick Example

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(wait_timeout=30, sleep=5, func=my_check_function):
    if sample:
        break
```

This calls `my_check_function()` every 5 seconds for up to 30 seconds. As soon as it returns a truthy value, the loop breaks. If 30 seconds elapse without success, a `TimeoutExpiredError` is raised.

## Step-by-Step: Polling Until a Condition Is Met

### 1. Import `TimeoutSampler`

```python
from timeout_sampler import TimeoutSampler
```

### 2. Create the sampler and iterate

Pass your function, a total timeout, and a sleep interval between polls:

```python
sampler = TimeoutSampler(
    wait_timeout=60,   # total seconds to wait
    sleep=3,           # seconds between each call
    func=check_api_health,
)
```

### 3. Write the polling loop

Each iteration calls your function and yields the return value. Check the value and `break` (or `return`) when you're satisfied:

```python
for sample in sampler:
    if sample == "healthy":
        print("Service is ready!")
        break
```

> **Warning:** If you never `break` out of the loop and the timeout expires, `TimeoutExpiredError` is raised automatically. Always include a break condition.

### 4. Handle the timeout

Wrap the loop in a `try`/`except` if you want to handle a timeout gracefully:

```python
from timeout_sampler import TimeoutExpiredError, TimeoutSampler

try:
    for sample in TimeoutSampler(wait_timeout=10, sleep=2, func=get_status):
        if sample == "ready":
            break
except TimeoutExpiredError:
    print("Timed out waiting for readiness")
```

### Passing Arguments to Your Function

Supply positional arguments with `func_args` and keyword arguments directly as extra keyword arguments:

```python
def check_endpoint(url, timeout=5):
    # ... returns True/False
    ...

for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=5,
    func=check_endpoint,
    func_args=("https://api.example.com/health",),
    timeout=5,
):
    if sample:
        break
```

- `func_args` — a tuple of positional arguments forwarded to `func`
- Any extra keyword arguments (like `timeout=5` above) are forwarded to `func` as `**kwargs`

### Evaluating Non-Boolean Return Values

The yielded `sample` is whatever your function returns. You can apply any condition, not just truthiness:

```python
for sample in TimeoutSampler(wait_timeout=60, sleep=2, func=get_pod_count):
    if sample is not None and sample >= 3:
        print(f"Reached {sample} pods")
        break
```

## Advanced Usage

### Ignoring Specific Exceptions

By default, `TimeoutSampler` uses `{Exception: []}` as its exception dictionary, which catches and ignores all exceptions raised by your function during polling. To be more selective, pass `exceptions_dict`:

```python
for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=2,
    func=fetch_data,
    exceptions_dict={ConnectionError: [], TimeoutError: []},
):
    if sample:
        break
```

- An empty list `[]` means "ignore this exception regardless of its message."
- A list of strings matches against the exception message text — only matching messages are ignored.

```python
exceptions_dict = {
    ConnectionError: ["connection refused", "reset by peer"],
    ValueError: [],  # ignore all ValueErrors
}
```

Any exception **not** listed (or listed but with a non-matching message) is immediately re-raised as a `TimeoutExpiredError`.

For full details on exception filtering, see [Filtering and Handling Exceptions](handling-exceptions.html) and [How Exception Matching Works](exception-matching-logic.html).

### Controlling Log Output

`TimeoutSampler` logs elapsed time and function details by default. Disable or customize logging with these flags:

| Parameter         | Type   | Default | Effect                                              |
|-------------------|--------|---------|-----------------------------------------------------|
| `print_log`       | `bool` | `True`  | Log elapsed time on each iteration                  |
| `print_func_log`  | `bool` | `True`  | Include function name and module in log messages     |
| `print_func_args` | `bool` | `True`  | Include function arguments in log (when `print_func_log` is `True`) |

```python
for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=5,
    func=my_func,
    print_log=False,        # suppress all elapsed-time logging
    print_func_log=False,   # suppress function call details
):
    if sample:
        break
```

See [Controlling Log Output](controlling-logging.html) for more on logging behavior.

### Using the `@retry` Decorator Instead

If your polling loop always follows the simple pattern of "break when truthy," the `@retry` decorator provides a more compact alternative:

```python
from timeout_sampler import retry

@retry(wait_timeout=10, sleep=2)
def wait_for_ready():
    return check_readiness()
```

This is equivalent to writing the `TimeoutSampler` loop manually. See [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html) for full decorator usage.

### Accessing Error Details After Timeout

When `TimeoutExpiredError` is raised, it carries diagnostic attributes:

```python
try:
    for sample in TimeoutSampler(wait_timeout=5, sleep=1, func=flaky_call):
        if sample:
            break
except TimeoutExpiredError as err:
    print(err)                # Human-readable message with elapsed time
    print(err.last_exp)       # The last exception raised by func (or None)
    print(err.elapsed_time)   # Seconds elapsed before timeout
```

See [TimeoutExpiredError Reference](api-exceptions.html) for the full exception API.

## Troubleshooting

**`TimeoutExpiredError` raised immediately**
Your `wait_timeout` is too short relative to how long `func` takes to execute. Ensure `wait_timeout` is large enough to allow at least one full call-and-sleep cycle.

**Exceptions from my function are silently swallowed**
The default `exceptions_dict` is `{Exception: []}`, which catches *everything*. Pass a narrower dictionary to let unexpected exceptions propagate. See [Filtering and Handling Exceptions](handling-exceptions.html).

**Loop never breaks even though my function returns data**
Make sure your break condition actually matches the return value. Yielded samples are the *exact* return value of your function — check for `None`, empty collections, or `0` if those are possible returns.

> **Tip:** For a full constructor reference including types and defaults, see [TimeoutSampler API](api-timeout-sampler.html).

## Related Pages

- [Getting Started with timeout-sampler](quickstart.html)
- [TimeoutSampler API](api-timeout-sampler.html)
- [Filtering and Handling Exceptions](handling-exceptions.html)
- [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html)
- [Common Polling Patterns](common-polling-patterns.html)
