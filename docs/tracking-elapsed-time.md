# Tracking Elapsed Time with TimeoutWatch

Track how much time remains in a custom polling loop, orchestration workflow, or multi-step operation using `TimeoutWatch` — a lightweight countdown timer that starts when you create it.

## Prerequisites

- `timeout-sampler` installed in your project (see [Getting Started with timeout-sampler](quickstart.html))

## Quick Example

```python
from timeout_sampler import TimeoutWatch

watch = TimeoutWatch(timeout=30)

while watch.remaining_time() > 0:
    result = do_something()
    if result:
        break
```

`TimeoutWatch` records the current time when instantiated and returns how many seconds are left each time you call `remaining_time()`.

## Step-by-Step Usage

### 1. Create a TimeoutWatch

Pass the total number of seconds you want to track:

```python
from timeout_sampler import TimeoutWatch

watch = TimeoutWatch(timeout=60)
```

The countdown starts immediately — there is no separate `start()` call.

### 2. Check Remaining Time

Call `remaining_time()` to get the seconds left:

```python
seconds_left = watch.remaining_time()
print(f"{seconds_left:.1f} seconds remaining")
```

- Returns a `float` when time remains.
- Returns `0` once the timeout has elapsed (it never returns a negative value).

### 3. Use in a Loop

Build a polling loop that runs until the timeout expires:

```python
from timeout_sampler import TimeoutWatch

watch = TimeoutWatch(timeout=10)

while watch.remaining_time() > 0:
    status = check_service_health()
    if status == "ready":
        print("Service is up!")
        break
    time.sleep(1)
else:
    print("Timed out waiting for service.")
```

> **Tip:** The `while`/`else` pattern in Python lets you run the `else` block only when the loop condition becomes false — a clean way to handle timeouts without extra flags.

### 4. Calculate Elapsed Time

Since `TimeoutWatch` tracks remaining time, you can derive how much time has passed:

```python
watch = TimeoutWatch(timeout=30)

# ... some work ...

elapsed = watch.timeout - watch.remaining_time()
print(f"Elapsed: {elapsed:.2f}s")
```

This is the same technique that `TimeoutSampler` uses internally to report elapsed time in its logs.

## API Reference

### `TimeoutWatch(timeout)`

| Parameter | Type    | Description                          |
|-----------|---------|--------------------------------------|
| `timeout` | `float` | Total countdown duration in seconds |

Creates a new watch and records the start time immediately.

### `remaining_time()`

```python
def remaining_time(self) -> int | float
```

Returns the number of seconds left until the timeout expires. The return value is clamped to `0` — it will never be negative.

| Condition                      | Return value            |
|-------------------------------|-------------------------|
| Called before timeout expires | Positive `float`        |
| Called after timeout expires  | `0`                     |

## Advanced Usage

### Coordinating Multiple Steps Under One Budget

When you need several sequential operations to fit within a shared time budget, create one `TimeoutWatch` and pass its remaining time to each step:

```python
from timeout_sampler import TimeoutSampler, TimeoutWatch

overall = TimeoutWatch(timeout=120)

# Step 1: Wait for database
for sample in TimeoutSampler(
    wait_timeout=overall.remaining_time(),
    sleep=2,
    func=check_database,
):
    if sample:
        break

# Step 2: Wait for cache (uses whatever time is left)
for sample in TimeoutSampler(
    wait_timeout=overall.remaining_time(),
    sleep=2,
    func=check_cache,
):
    if sample:
        break
```

Each `TimeoutSampler` receives only the remaining portion of the overall budget, so the total wall-clock time never exceeds 120 seconds regardless of how long step 1 takes.

> **Note:** If `remaining_time()` returns `0` before a step begins, the `TimeoutSampler` will raise a `TimeoutExpiredError` immediately. See [TimeoutExpiredError Reference](api-exceptions.html) for details on that exception.

### Passing Fractional Timeouts

`TimeoutWatch` accepts `float` values, so sub-second precision works out of the box:

```python
watch = TimeoutWatch(timeout=0.5)
# Half-second budget
```

### Using TimeoutWatch Without TimeoutSampler

`TimeoutWatch` has no dependency on `TimeoutSampler` — use it anywhere you need a simple countdown:

```python
from timeout_sampler import TimeoutWatch

watch = TimeoutWatch(timeout=5)

items = get_work_items()
for item in items:
    if watch.remaining_time() == 0:
        print("Time budget exhausted, stopping early.")
        break
    process(item)
```

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `remaining_time()` returns `0` immediately | `timeout` was set to `0` or a negative value | Use a positive `timeout` value |
| Elapsed time calculation seems wrong | You created the `TimeoutWatch` too early (e.g., at module import time) | Create the instance right before the work begins |
| Loop never exits | Your loop body doesn't call `remaining_time()` on each iteration | Ensure the `while` condition re-evaluates `remaining_time()` every pass |

## Related Pages

- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html) — the primary polling interface that uses `TimeoutWatch` under the hood
- [TimeoutWatch API](api-timeout-watch.html) — full constructor and method reference
- [TimeoutExpiredError Reference](api-exceptions.html) — the exception raised when time runs out

## Related Pages

- [TimeoutWatch API](api-timeout-watch.html)
- [Polling a Function with TimeoutSampler](polling-with-timeout-sampler.html)
- [TimeoutSampler API](api-timeout-sampler.html)
- [TimeoutExpiredError Reference](api-exceptions.html)
- [Common Polling Patterns](common-polling-patterns.html)
