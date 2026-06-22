# Common Polling Patterns

Copy-paste recipes for the most frequent `timeout-sampler` use cases. Each recipe is self-contained and ready to drop into your project.

> **Note:** All recipes assume you have already installed the package. See [Getting Started with timeout-sampler](quickstart.html) for installation instructions.

## Wait for an API to Become Ready

Poll an HTTP endpoint until it returns a successful response.

```python
import requests
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=120,
    sleep=5,
    func=lambda: requests.get("http://localhost:8080/healthz").ok,
    exceptions_dict={requests.ConnectionError: [], requests.Timeout: []},
):
    if sample:
        break
```

The sampler calls the health-check endpoint every 5 seconds for up to 2 minutes. Connection errors and timeouts are silently retried thanks to `exceptions_dict`. The loop breaks as soon as the endpoint returns a 2xx response.

> **Tip:** For long startup waits, increase `wait_timeout` and keep `sleep` between 2–10 seconds to avoid hammering the service.

## Retry a Flaky Function with the @retry Decorator

Automatically re-run a function until it returns a truthy value.

```python
from timeout_sampler import retry

@retry(wait_timeout=30, sleep=2)
def fetch_cluster_status():
    import requests
    resp = requests.get("https://api.example.com/cluster/status")
    resp.raise_for_status()
    return resp.json()["state"] == "ready"

# Raises TimeoutExpiredError after 30s if the cluster never reaches "ready"
fetch_cluster_status()
```

The `@retry` decorator wraps the function in a `TimeoutSampler` loop and returns the first truthy result. Use it when you want polling behavior without writing the iteration yourself.

- The decorated function keeps its original signature — pass arguments as usual.
- Any unhandled exception is immediately re-raised unless you add `exceptions_dict`.

See [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html) for full parameter details.

## Poll with a Partial Function

Use `functools.partial` to poll a function that requires arguments without using `func_args` or keyword arguments.

```python
from functools import partial
from timeout_sampler import TimeoutSampler

def check_pod_phase(namespace, pod_name):
    """Returns True when the pod is Running."""
    import subprocess, json
    result = subprocess.run(
        ["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "json"],
        capture_output=True, text=True,
    )
    pod = json.loads(result.stdout)
    return pod["status"]["phase"] == "Running"

poll_fn = partial(check_pod_phase, "default", "my-app-pod-7f4b9")

for sample in TimeoutSampler(wait_timeout=90, sleep=3, func=poll_fn):
    if sample:
        break
```

`TimeoutSampler` resolves `partial` objects automatically when building log output, so function names and modules are logged correctly even through the wrapper. This pattern keeps the sampler call clean when the polled function has many parameters.

## Pass Arguments via func_args and Keyword Arguments

Provide positional and keyword arguments directly to `TimeoutSampler` without wrapping in `partial`.

```python
from timeout_sampler import TimeoutSampler

def is_file_present(directory, filename, min_size_bytes=0):
    import os
    path = os.path.join(directory, filename)
    return os.path.isfile(path) and os.path.getsize(path) >= min_size_bytes

for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=2,
    func=is_file_present,
    func_args=("/tmp/exports", "report.csv"),
    min_size_bytes=1024,
):
    if sample:
        break
```

Positional arguments go into `func_args` as a tuple. Keyword arguments are passed directly as extra kwargs to the `TimeoutSampler` constructor, which forwards them to `func` on every call.

## Ignore All Instances of an Exception

Swallow every occurrence of a specific exception type during polling.

```python
from timeout_sampler import TimeoutSampler

def get_resource():
    import json, urllib.request
    resp = urllib.request.urlopen("http://localhost:9090/resource")
    return json.loads(resp.read())

for sample in TimeoutSampler(
    wait_timeout=30,
    sleep=2,
    func=get_resource,
    exceptions_dict={ConnectionError: [], TimeoutError: []},
):
    if sample:
        break
```

An empty list `[]` next to an exception class means *ignore all messages* for that exception. The sampler will keep retrying regardless of the exception's text content.

See [Filtering and Handling Exceptions](handling-exceptions.html) for a full explanation of `exceptions_dict`.

## Filter Exceptions by Message Text

Only ignore exceptions whose message matches specific substrings.

```python
from timeout_sampler import TimeoutSampler

def query_database():
    import sqlite3
    conn = sqlite3.connect("/var/data/app.db")
    cursor = conn.execute("SELECT count(*) FROM jobs WHERE status = 'done'")
    count = cursor.fetchone()[0]
    conn.close()
    if count == 0:
        raise RuntimeError("no completed jobs yet")
    return count

for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=5,
    func=query_database,
    exceptions_dict={RuntimeError: ["no completed jobs yet"]},
):
    if sample:
        print(f"Completed jobs: {sample}")
        break
```

The sampler checks whether the raised exception's string representation *contains* any of the listed substrings. If a `RuntimeError` is raised with a different message (e.g., `"database locked"`), it will **not** be caught — it will immediately raise a `TimeoutExpiredError`.

> **Warning:** Message matching uses substring `in` checks, not exact equality. The filter `"not found"` will also match `"resource not found in namespace"`.

## Combine Multiple Exception Filters

Handle several exception types, each with independent message filters.

```python
from timeout_sampler import TimeoutSampler

def provision_vm():
    """Calls a cloud API that may fail in multiple ways."""
    # ... cloud SDK call ...
    return {"id": "vm-abc123", "status": "running"}

for sample in TimeoutSampler(
    wait_timeout=300,
    sleep=10,
    func=provision_vm,
    exceptions_dict={
        ConnectionError: [],                          # retry on any connection issue
        TimeoutError: [],                             # retry on any timeout
        RuntimeError: ["quota exceeded", "retryable"],  # only retry these messages
        PermissionError: ["token expired"],            # only retry on expired tokens
    },
):
    if sample and sample.get("status") == "running":
        print(f"VM provisioned: {sample['id']}")
        break
```

Each exception class has its own message filter list. This lets you broadly retry transient network errors while being selective about application-level exceptions. Any exception type or message **not** listed will immediately surface as a `TimeoutExpiredError`.

See [How Exception Matching Works](exception-matching-logic.html) for the inheritance-aware matching algorithm.

## Leverage Exception Inheritance for Broad Matching

Catch a parent exception class to automatically cover all its subclasses.

```python
from timeout_sampler import TimeoutSampler

class ServiceError(Exception):
    pass

class TransientError(ServiceError):
    pass

class RateLimitError(ServiceError):
    pass

def call_external_service():
    # ... API call that may raise TransientError or RateLimitError ...
    return True

for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=3,
    func=call_external_service,
    exceptions_dict={ServiceError: []},
):
    if sample:
        break
```

Listing `ServiceError` in `exceptions_dict` catches both `TransientError` and `RateLimitError` because `TimeoutSampler` uses `isinstance()` to match exceptions. You don't need to enumerate every subclass individually.

> **Tip:** Use broad parent-class matching for exception hierarchies you control, and specific-class matching for third-party exceptions where you want precise control.

## Wait for a Return Value to Match a Condition

Poll until the function returns a specific value, not just a truthy one.

```python
from timeout_sampler import TimeoutSampler

def get_deployment_replicas():
    """Returns the current number of ready replicas."""
    import subprocess, json
    result = subprocess.run(
        ["kubectl", "get", "deployment", "web-api", "-o", "json"],
        capture_output=True, text=True,
    )
    deploy = json.loads(result.stdout)
    return deploy["status"].get("readyReplicas", 0)

desired_replicas = 3

for sample in TimeoutSampler(wait_timeout=120, sleep=5, func=get_deployment_replicas):
    if sample == desired_replicas:
        break
```

The `if` condition inside the loop is your match logic — you can check equality, membership, ranges, or any predicate. The sampler itself only yields; your code decides what constitutes success.

## Silence All Log Output

Disable logging for test suites or inner loops where verbosity is unwanted.

```python
from timeout_sampler import TimeoutSampler

for sample in TimeoutSampler(
    wait_timeout=10,
    sleep=1,
    func=lambda: True,
    print_log=False,
    print_func_log=False,
):
    if sample:
        break
```

Setting `print_log=False` suppresses elapsed-time messages, and `print_func_log=False` suppresses function call details. Use both together for completely silent polling.

See [Controlling Log Output](controlling-logging.html) for fine-grained logging options including `print_func_args`.

## Track Remaining Time Across Multiple Polling Steps

Use `TimeoutWatch` to share a single time budget across sequential polling operations.

```python
from timeout_sampler import TimeoutSampler, TimeoutWatch

overall_timeout = TimeoutWatch(timeout=120)

# Step 1: Wait for database
for sample in TimeoutSampler(
    wait_timeout=overall_timeout.remaining_time(),
    sleep=3,
    func=lambda: __import__("os").path.exists("/tmp/db.ready"),
):
    if sample:
        break

# Step 2: Wait for cache (uses remaining time from same budget)
for sample in TimeoutSampler(
    wait_timeout=overall_timeout.remaining_time(),
    sleep=2,
    func=lambda: __import__("os").path.exists("/tmp/cache.ready"),
):
    if sample:
        break

print(f"Both ready with {overall_timeout.remaining_time():.1f}s to spare")
```

`TimeoutWatch.remaining_time()` returns the seconds left from the original timeout, automatically accounting for elapsed time. Pass it as `wait_timeout` to give each subsequent step only the remaining budget.

See [Tracking Elapsed Time with TimeoutWatch](tracking-elapsed-time.html) for the full `TimeoutWatch` API.

## Catch TimeoutExpiredError and Inspect the Last Exception

Access diagnostic information when polling fails.

```python
from timeout_sampler import TimeoutExpiredError, TimeoutSampler

def unstable_lookup():
    raise ConnectionError("connection refused on port 5432")

try:
    for sample in TimeoutSampler(
        wait_timeout=10,
        sleep=2,
        func=unstable_lookup,
        exceptions_dict={ConnectionError: []},
    ):
        if sample:
            break
except TimeoutExpiredError as e:
    print(f"Polling failed: {e}")
    print(f"Last exception type: {type(e.last_exp).__name__}")  # ConnectionError
    print(f"Last exception message: {e.last_exp}")              # connection refused on port 5432
    print(f"Total elapsed time: {e.elapsed_time}s")
```

`TimeoutExpiredError` exposes `last_exp` (the last exception raised by the polled function) and `elapsed_time` (total seconds spent polling). Use these for detailed error reporting or conditional recovery logic.

See [TimeoutExpiredError Reference](api-exceptions.html) for all available attributes.

## Related Pages

- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [Retrying Functions with the @retry Decorator](using-the-retry-decorator.html)
- [Filtering and Handling Exceptions](handling-exceptions.html)
- [Tracking Elapsed Time with TimeoutWatch](tracking-elapsed-time.html)
- [How Exception Matching Works](exception-matching-logic.html)
