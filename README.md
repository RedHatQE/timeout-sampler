# TimeoutSampler

Utility class for waiting to any function output and interact with it in given time.

## Installation

```bash
pip3 install timeout-sampler
```

## Usage

```python
from random import randint
from timeout_sampler import TimeoutSampler


def random_number(start, end):
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
```
