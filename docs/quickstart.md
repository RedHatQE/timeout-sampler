## Prerequisites

- Python 3.9 or later
- `pip` (or any Python package manager)

## Install

```bash
pip install timeout-sampler
```

## Quick Example

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(wait_timeout=10, sleep=2, func=lambda: True):
    if sample:
        print("Got a truthy value, done!")
        break
```

That's it — `TimeoutSampler` calls your function every `sleep` seconds. Each iteration yields the return value so you can inspect it. If `wait_timeout` seconds elapse without a `break`, a `TimeoutExpiredError` is raised.

## Step-by-Step Walkthrough

### 1. Import the essentials

```python
from timeout_sampler import TimeoutSampler, TimeoutExpiredError
```

### 2. Define the function you want to poll

Any callable works — a regular function, a lambda, or a method:

```python
import random

def check_service():
    """Simulate a service that becomes ready after a few attempts."""
    return random.random() > 0.7
```

### 3. Create the sampler and iterate

```python
sampler = TimeoutSampler(
    wait_timeout=30,   # total seconds to wait
    sleep=5,           # seconds between retries
    func=check_service,
)

for sample in sampler:
    if sample:
        print("Service is ready!")
        break
```

If `check_service()` never returns a truthy value within 30 seconds, a `TimeoutExpiredError` is raised automatically after the loop ends.

### 4. Handle the timeout

Wrap the loop in a `try`/`except` when you need to react to a timeout:

```python
try:
    for sample in TimeoutSampler(wait_timeout=10, sleep=2, func=check_service):
        if sample:
            break
except TimeoutExpiredError as e:
    print(f"Timed out: {e}")
```

`TimeoutExpiredError` exposes two useful attributes:

| Attribute      | Type               | Description                                      |
|----------------|--------------------|--------------------------------------------------|
| `last_exp`     | `Exception | None` | The last exception raised inside `func`, if any  |
| `elapsed_time` | `float | None`     | Seconds elapsed before the error was raised       |

### 5. Pass arguments to your function

Use keyword arguments directly on the `TimeoutSampler` constructor — they are forwarded to `func`:

```python
def is_ready(host, port):
    # ... check connection ...
    return True

for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=5,
    func=is_ready,
    host="localhost",
    port=8080,
):
    if sample:
        break
```

## Use the `@retry` Decorator

For the common pattern of "poll until truthy, then return the value," the `@retry` decorator eliminates the `for` loop entirely:

```python
from timeout_sampler import retry

@retry(wait_timeout=10, sleep=2)
def get_value():
    # return a truthy value when ready
    return True

result = get_value()  # blocks until truthy or TimeoutExpiredError
```

If `get_value()` keeps returning a falsy value for 10 seconds, `TimeoutExpiredError` is raised. See [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html) for full decorator options.

## Advanced Usage

### Handling exceptions during polling

By default, `TimeoutSampler` catches **all** exceptions raised inside `func` and keeps retrying. You can control this with `exceptions_dict`:

```python
for sample in TimeoutSampler(
    wait_timeout=20,
    sleep=3,
    func=check_service,
    exceptions_dict={ConnectionError: []},
):
    if sample:
        break
```

- `{ConnectionError: []}` — ignore all `ConnectionError` instances (and subclasses) and keep polling.
- `{ConnectionError: ["refused"]}` — only ignore a `ConnectionError` whose message contains `"refused"`; any other `ConnectionError` re-raises immediately.
- `{}` — do **not** ignore any exceptions; every exception re-raises immediately.

> **Warning:** Passing an empty dict `{}` means *no* exceptions are caught. If you want to catch all exceptions (the default), omit `exceptions_dict` entirely or pass `{Exception: []}`.

See [Filtering and Handling Exceptions](handling-exceptions.html) for the full inheritance-aware matching rules.

### Controlling log output

`TimeoutSampler` logs elapsed time and function call details by default. Toggle these with three boolean flags:

| Parameter         | Default | Effect                                                 |
|-------------------|---------|--------------------------------------------------------|
| `print_log`       | `True`  | Log elapsed time on each iteration                     |
| `print_func_log`  | `True`  | Include function name and module in log messages       |
| `print_func_args` | `True`  | Include `args`/`kwargs` in the function log            |

```python
for sample in TimeoutSampler(
    wait_timeout=10,
    sleep=2,
    func=check_service,
    print_log=False,        # silence all log output
):
    if sample:
        break
```

See [Controlling Log Output](controlling-logging.html) for details.

### Tracking elapsed time independently

The `TimeoutWatch` helper lets you build custom timing logic outside of `TimeoutSampler`:

```python
from timeout_sampler import TimeoutWatch

watch = TimeoutWatch(timeout=60.0)

while watch.remaining_time() > 0:
    # your custom logic here
    pass
```

See [Tracking Elapsed Time with TimeoutWatch](tracking-elapsed-time.html) for more.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `TimeoutExpiredError` raised immediately | `wait_timeout` is too small or `0` | Increase `wait_timeout` to allow at least one poll cycle |
| Function arguments not reaching `func` | Passing args positionally | Pass arguments as **keyword arguments** on the `TimeoutSampler` constructor (e.g., `host="localhost"`) |
| All exceptions are silently swallowed | Default `exceptions_dict` is `{Exception: []}` | Pass a narrower `exceptions_dict` to only ignore expected exceptions |
| Loop never exits | `func` returns truthy but there is no `break` | Always `break` (or `return`) out of the `for` loop when you get the value you want |

> **Tip:** For copy-paste recipes covering common real-world scenarios, see [Common Polling Patterns](common-polling-patterns.html).

## Related Pages

- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html)
- [Filtering and Handling Exceptions](handling-exceptions.html)
- [Common Polling Patterns](common-polling-patterns.html)
- [TimeoutSampler API](api-timeout-sampler.html)
