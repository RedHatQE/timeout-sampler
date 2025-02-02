# TimeoutSampler

Utility class for waiting to any function output and interact with it in given time.

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

# Raise TimeoutExpiredError immediately since TypeError was raised
for sample in TimeoutSampler(
    wait_timeout=1,
    sleep=1,
    func=raise_value_error,
    raise_on_exceptions={TypeError: []},
    start="1",
    end="10",
):
    if sample:
        return
# Raise TimeoutExpiredError immediately since TypeError with matching error was raised
for sample in TimeoutSampler(
    wait_timeout=1,
    sleep=1,
    func=raise_value_error,
    raise_on_exceptions={TypeError: ["Start and end must be int type"]},
    start="1",
    end="10",
):
    if sample:
        return

# Raise TimeoutExpiredError after timeout since TypeError error do not match the error in exceptions_dict
for sample in TimeoutSampler(
    wait_timeout=1,
    sleep=1,
    func=raise_value_error,
    raise_on_exceptions={TypeError: ["Some other error"]},
    start="1",
    end="10",
):
    if sample:
        return

# Use as decorator. (Any argument that TimeoutSampler accepts will be passed to the decorated function)
from timeout_sampler import retry

@retry(wait_timeout=60, sleep=1)
def random_number(start, end):
    if isinstance(start, str) or isinstance(end, str):
      raise TypeError("start and end must be int type")

    if end > start:
      raise ValueError("End must be greater than start")

    return randint(start, end)
```
