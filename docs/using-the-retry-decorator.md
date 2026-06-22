# Retrying Functions with the @retry Decorator

You want to automatically retry a function until it returns a truthy value—without writing a manual polling loop. The `@retry` decorator wraps your function so it keeps calling itself on an interval until it succeeds or a timeout expires.

## Prerequisites

- `timeout-sampler` installed in your environment. See [Getting Started with timeout-sampler](quickstart.html) for installation steps.
- Basic familiarity with Python decorators.

## Quick Example

```python
from timeout_sampler import retry

@retry(wait_timeout=30, sleep=5)
def check_service_health():
    response = requests.get("https://my-service/health")
    return response.status_code == 200

# Blocks until the function returns True or 30 seconds elapse
check_service_health()
```

That's it — the decorator handles all the polling. If `check_service_health()` doesn't return a truthy value within 30 seconds, a `TimeoutExpiredError` is raised.

## How It Works

1. **Decorate** your function with `@retry(wait_timeout=..., sleep=...)`.
2. **Call** the function normally — arguments are passed through.
3. The decorator calls your function every `sleep` seconds.
4. As soon as the function returns a **truthy** value, that value is returned to the caller.
5. If the timeout expires without a truthy return, `TimeoutExpiredError` is raised.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `wait_timeout` | `int` | *(required)* | Maximum seconds to keep retrying |
| `sleep` | `int` | *(required)* | Seconds to wait between each attempt |
| `exceptions_dict` | `dict` | `None` | Exceptions to tolerate during polling |
| `print_log` | `bool` | `True` | Log elapsed time to console |
| `print_func_log` | `bool` | `True` | Log function call details |
| `print_func_args` | `bool` | `True` | Include arguments in the function log |

> **Tip:** For a complete parameter reference, see [@retry Decorator API](api-retry-decorator.html).

## Step-by-Step: Retrying Until a Condition Is Met

### 1. Define your function

Write a function that returns a truthy value on success and a falsy value (e.g., `False`, `None`, `0`, `""`) on failure.

```python
def is_database_ready():
    status = db.get_status()
    return status == "ready"
```

### 2. Apply the decorator

```python
from timeout_sampler import retry

@retry(wait_timeout=60, sleep=2)
def is_database_ready():
    status = db.get_status()
    return status == "ready"
```

### 3. Call the function

```python
is_database_ready()
print("Database is ready!")
```

### 4. Handle timeout

```python
from timeout_sampler import TimeoutExpiredError

try:
    is_database_ready()
except TimeoutExpiredError:
    print("Database did not become ready in time")
```

## Passing Arguments

The decorator passes through all positional and keyword arguments to your function:

```python
from timeout_sampler import retry

@retry(wait_timeout=30, sleep=3)
def wait_for_pod(namespace, name, status="Running"):
    pod = get_pod(namespace, name)
    return pod.status == status

# Arguments are forwarded to the decorated function
wait_for_pod("default", "my-pod", status="Running")
```

## Returning Values

When the function returns a truthy value, that value is returned to the caller—not just `True`:

```python
@retry(wait_timeout=20, sleep=2)
def fetch_result():
    result = get_async_result()
    return result  # Returns the actual result object when truthy

data = fetch_result()
print(data)  # The truthy value your function returned
```

> **Warning:** If your function returns a value that Python considers falsy (e.g., `0`, empty list `[]`, empty string `""`), the decorator treats it as a failed attempt and keeps retrying. Make sure success cases return a truthy value.

## Advanced Usage

### Tolerating Specific Exceptions

Use `exceptions_dict` to tell the decorator which exceptions should be ignored during polling instead of stopping execution. The keys are exception classes, and the values are lists of substring patterns to match against the exception message. An empty list matches all messages for that exception type.

```python
@retry(
    wait_timeout=30,
    sleep=5,
    exceptions_dict={ConnectionError: []},
)
def connect_to_service():
    return requests.get("https://my-service/api").ok
```

This keeps retrying even when `ConnectionError` is raised—useful for services that are still starting up.

You can also filter by exception message:

```python
@retry(
    wait_timeout=30,
    sleep=5,
    exceptions_dict={ConnectionError: ["Connection refused"]},
)
def connect_to_service():
    return requests.get("https://my-service/api").ok
```

Only `ConnectionError` exceptions containing `"Connection refused"` in their message text are tolerated. Other `ConnectionError` messages will stop polling.

> **Note:** For a detailed explanation of how exception matching and inheritance work, see [How Exception Matching Works](exception-matching-logic.html). For more `exceptions_dict` patterns, see [Filtering and Handling Exceptions](handling-exceptions.html).

### Controlling Log Output

By default, the decorator logs timing information and function details. You can turn these off individually:

```python
@retry(
    wait_timeout=10,
    sleep=1,
    print_log=False,       # Suppress all elapsed-time logs
)
def quiet_check():
    return some_condition()
```

```python
@retry(
    wait_timeout=10,
    sleep=1,
    print_func_log=False,  # Suppress function name in logs
    print_func_args=False,  # Suppress argument values in logs
)
def check_with_secrets(api_key):
    return validate(api_key)
```

> **Tip:** For more detail on logging options, see [Controlling Log Output](controlling-logging.html).

### When to Use @retry vs. TimeoutSampler

| | `@retry` | `TimeoutSampler` |
|---|---|---|
| **Best for** | Simple "retry until truthy" cases | Custom logic on each iteration |
| **Success condition** | Any truthy return value | You define it in the loop body |
| **Access to each result** | No — only the final truthy value | Yes — you inspect every yielded value |
| **Code style** | Decorator on function definition | Explicit `for` loop |

Use `@retry` when you just need a function to keep trying. Use `TimeoutSampler` when you need to examine intermediate results or apply complex success logic. See [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html) for the iterator approach.

## Troubleshooting

**`TimeoutExpiredError` is raised even though my function works**

Your function may be returning a falsy value on success. Check that it returns something truthy (e.g., `True`, a non-empty object) when the operation succeeds.

**Polling seems to stop too early when exceptions occur**

If your function raises an exception that isn't listed in `exceptions_dict`, polling will stop. Add the exception class to `exceptions_dict` to tolerate it. See [Filtering and Handling Exceptions](handling-exceptions.html) for details.

**Logs are too noisy**

Set `print_log=False` to suppress timing output, or set `print_func_args=False` to hide sensitive argument values. See [Controlling Log Output](controlling-logging.html).

## Related Pages

- [@retry Decorator API](api-retry-decorator.html)
- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [Filtering and Handling Exceptions](handling-exceptions.html)
- [Controlling Log Output](controlling-logging.html)
- [How Exception Matching Works](exception-matching-logic.html)
