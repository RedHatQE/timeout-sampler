# TimeoutSampler

Utility class for waiting to any function output and interact with it in given time.

📖 **[Full Documentation](https://redhatqe.github.io/timeout-sampler/)**

## Installation

```bash
python3 -m pip install timeout-sampler
```

## Usage

```python
from random import randint
from timeout_sampler import TimeoutSampler


def random_number(start, end):
    if isinstance(start, str) or isinstance(end, str):
        raise TypeError("start and end must be int type")

    if end <= start:
        raise ValueError("End must be greater than start")

    return randint(start, end)


samples = TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=random_number,
    start=1,
    end=10,
)
for sample in samples:
    if sample == 5:
        break

# Raise `TimeoutExpiredError` since we continue on `ValueError` exception
for sample in TimeoutSampler(
    wait_timeout=1,
    sleep=1,
    func=random_number,
    exceptions_dict={ValueError: []},
    start=10,
    end=1,
):
    if sample:
        return

# Raise `TimeoutExpiredError` since we continue on `ValueError` with match error exception
for sample in TimeoutSampler(
    wait_timeout=1,
    sleep=1,
    func=raise_value_error,
    exceptions_dict={ValueError: ["End must be greater than start"]},
    start=10,
    end=1,
):
    if sample:
        return

# Raise TimeoutExpiredError immediately since ValueError exception error do not match the error in the exceptions_dict
for sample in TimeoutSampler(
    wait_timeout=1,
    sleep=1,
    func=raise_value_error,
    exceptions_dict={ValueError: ["some other error"]},
    start=10,
    end=1,
):
    if sample:
        return


# Use callable filters to retry based on exception attributes.
# Callables receive the exception and should return a truthy value to ignore (retry).
# Example: HttpError is a custom exception with a `status` attribute,
# and make_request() is a function that may raise it.
# Only retry on HTTP 5xx errors; 4xx errors raise immediately.
for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=make_request,
    exceptions_dict={HttpError: [lambda exc: exc.status >= 500]},
):
    if sample:
        break

# Callable and string filters can be combined in the same list.
for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=make_request,
    exceptions_dict={HttpError: ["connection refused", lambda exc: exc.status >= 500]},
):
    if sample:
        break


# Sensitive kwargs (Authorization, token, password, etc.) are automatically
# redacted from log output. You can customize which keys are redacted:
for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=make_request,
    headers={"Authorization": "Bearer my-secret-token"},
):
    if sample:
        break
# Log output will show: Kwargs: {'headers': {'Authorization': '***'}}

# To add custom sensitive keys (merged with defaults):
for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=call_api,
    sensitive_keys=frozenset({"x-custom-secret"}),
    headers={"Authorization": "Bearer token", "x-custom-secret": "value"},  # pragma: allowlist secret
):
    if sample:
        break


# wait_for_ssh must return a truthy value when SSH is reachable.
def wait_for_ssh(host):
    return check_ssh(host)  # raises ConnectionError while SSH is down


# When print_log=True (default), each finished wait logs one outcome line:
#   {label} succeeded after 12.3 [0:00:12.300000].
#   {label} failed after 3.1 [0:00:03.100000]. [last exception: ...]
#   {label} timed out after 60.0 [0:01:00]. [last exception: ...]
#   {label} timed out after 60.0 [0:01:00].
# The [last exception: ...] suffix is only added when an exception was captured
# (omitted for timeouts caused by repeated falsy returns with no raise).
# The label is log_context when set, otherwise "Function: module.function"
# (same Function: marker as the waiting log). Retried exceptions are not logged.

# Use log_context for a custom outcome label instead of Function: module.function.
for sample in TimeoutSampler(
    wait_timeout=60,
    sleep=1,
    func=wait_for_ssh,
    host="my-vm",
    log_context="SSH connectivity to my-vm",
    exceptions_dict={ConnectionError: []},
):
    if sample:
        break
# On success: "SSH connectivity to my-vm succeeded after 12.3 [0:00:12.300000]."
# On non-retried error: "SSH connectivity to my-vm failed after 3.1 [0:00:03.100000]. [last exception: ...]"
# On timeout with last exception: "… timed out after 60.0 [0:01:00]. [last exception: ...]"
# On timeout with no exception (falsy returns): "… timed out after 60.0 [0:01:00]."


# Use as decorator. (Any argument that TimeoutSampler accepts will be passed to the decorated function)
from timeout_sampler import retry


@retry(wait_timeout=60, sleep=1, log_context="SSH connectivity to my-vm", exceptions_dict={ConnectionError: []})
def wait_for_ssh(host):
    return check_ssh(host)  # truthy when SSH is up; raises ConnectionError otherwise


@retry(wait_timeout=60, sleep=1)
def random_number(start, end):
    # Outcome line: "Function: mymodule.random_number succeeded after 12.3 [0:00:12.300000]."
    if isinstance(start, str) or isinstance(end, str):
        raise TypeError("start and end must be int type")

    if end <= start:
        raise ValueError("End must be greater than start")

    return randint(start, end)
```
