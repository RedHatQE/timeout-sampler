# TimeoutWatch API

## Overview

`TimeoutWatch` is a lightweight time-tracking class that records a start time on creation and computes remaining time on demand. It is used internally by [`TimeoutSampler`](api-timeout-sampler.html) and can be used independently in custom polling or orchestration workflows.

## Import

```python
from timeout_sampler import TimeoutWatch
```

## Class: `TimeoutWatch`

```python
class TimeoutWatch(timeout: float) -> None
```

A time counter that determines the time remaining since the start of a given interval. The clock starts immediately upon construction.

---

### Constructor

```python
TimeoutWatch(timeout: float)
```

Creates a new `TimeoutWatch` instance. Records the current time as the start time and stores the specified timeout duration.

#### Parameters

| Name      | Type    | Default | Description                                      |
|-----------|---------|---------|--------------------------------------------------|
| `timeout` | `float` | —       | Duration of the interval in seconds to track.     |

#### Attributes Set

| Attribute    | Type    | Description                                              |
|--------------|---------|----------------------------------------------------------|
| `timeout`    | `float` | The timeout duration passed to the constructor.           |
| `start_time` | `float` | The wall-clock time (`time.time()`) captured at creation. |

#### Example

```python
from timeout_sampler import TimeoutWatch

watch = TimeoutWatch(timeout=30)
print(watch.timeout)      # 30
print(watch.start_time)   # e.g. 1750600000.123456
```

---

### Method: `remaining_time`

```python
remaining_time() -> int | float
```

Returns the number of seconds remaining in the timeout interval, calculated as:

```
max(0, start_time + timeout - current_time)
```

The return value never goes below `0`.

#### Parameters

None.

#### Return Value

| Type          | Description                                                                 |
|---------------|-----------------------------------------------------------------------------|
| `int \| float` | Seconds remaining. Returns `0` (or `0.0`) once the timeout has elapsed.    |

#### Example

```python
import time
from timeout_sampler import TimeoutWatch

watch = TimeoutWatch(timeout=5)

time.sleep(2)
print(watch.remaining_time())  # ≈ 3.0

time.sleep(4)
print(watch.remaining_time())  # 0
```

#### Use in a Custom Polling Loop

```python
import time
from timeout_sampler import TimeoutWatch

watch = TimeoutWatch(timeout=10)

while watch.remaining_time() > 0:
    result = check_some_condition()
    if result:
        break
    time.sleep(1)
else:
    raise RuntimeError("Condition not met within 10 seconds")
```

> **Note:** `remaining_time()` is guaranteed to return `0` (never a negative value) once the timeout has elapsed. You can safely use `> 0` as the loop condition.

---

## Relationship to TimeoutSampler

`TimeoutSampler` creates a `TimeoutWatch` internally to manage its iteration deadline. If you need a polling loop with built-in exception handling and logging, use [`TimeoutSampler`](api-timeout-sampler.html) instead. Use `TimeoutWatch` directly when you need manual control over the polling logic.

For a usage-oriented walkthrough, see [Tracking Elapsed Time with TimeoutWatch](tracking-elapsed-time.html).

---

## Computing Elapsed Time

`TimeoutWatch` does not provide a dedicated elapsed-time method. Compute it by subtracting the remaining time from the original timeout:

```python
from timeout_sampler import TimeoutWatch

watch = TimeoutWatch(timeout=30)

# ... some work ...

elapsed = watch.timeout - watch.remaining_time()
print(f"Elapsed: {elapsed:.2f}s")
```

> **Tip:** This is the same pattern [`TimeoutSampler`](api-timeout-sampler.html) uses internally to populate the `elapsed_time` attribute on [`TimeoutExpiredError`](api-exceptions.html).

## Related Pages

- [Tracking Elapsed Time with TimeoutWatch](tracking-elapsed-time.html)
- [TimeoutSampler API](api-timeout-sampler.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [Common Polling Patterns](common-polling-patterns.html)
