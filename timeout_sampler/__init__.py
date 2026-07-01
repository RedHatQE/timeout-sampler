from __future__ import annotations

import datetime
import time
from collections.abc import Callable
from typing import Any

from simple_logger.logger import get_logger

LOGGER = get_logger(name=__name__)

ExceptionFilter = str | Callable[[Exception], bool]
ExceptionsDict = dict[type[Exception], list[ExceptionFilter]]

__all__ = ["ExceptionFilter", "ExceptionsDict", "TimeoutExpiredError", "TimeoutSampler", "TimeoutWatch", "retry"]


def _elapsed_time_log(elapsed_time: float) -> str:
    return f"Elapsed time: {elapsed_time} [{datetime.timedelta(seconds=elapsed_time)}]"


class TimeoutExpiredError(Exception):
    def __init__(self, value: str, last_exp: Exception | None = None, elapsed_time: float | None = None) -> None:
        super().__init__()
        self.value = value
        self.last_exp = last_exp
        self.elapsed_time = elapsed_time

    def __str__(self) -> str:
        msg = f"Timed Out: {self.value}."

        if self.elapsed_time:
            msg += f"\n{_elapsed_time_log(elapsed_time=self.elapsed_time)}"

        return msg


class TimeoutSampler:
    """
    Samples the function output.

    This is a generator object that at first yields the output of callable.
    After the yield, it either raises instance of `TimeoutExpiredError` or
    sleeps `sleep` seconds.

    Yielding the output allows you to handle every value as you wish.

    exceptions_dict:
        exceptions_dict should be in the following format:
        {
            exception0: [exception0_msg0],
            exception1: [
                exception1_msg0,
                exception1_msg1
            ],
            exception2: [],
            exception3: [lambda exc: exc.status >= 500]
        }

        Values can be strings (matched against str(exception)) or callables
        (invoked with the exception, returning True to ignore/retry).

        If an exception is raised within `func`:
            Example exception inheritance:
                class Exception
                class AExampleError(Exception)
                class BExampleError(AExampleError)

            The raised exception's class will fall into one of three categories:
                1. An exception class specifically declared in exceptions_dict
                    exceptions_dict: {BExampleError: []}
                    raise: BExampleError
                    result: continue

                2. A child class inherited from an exception class in exceptions_dict
                    exceptions_dict: {AExampleError: []}
                    raise: BExampleError
                    result: continue

                3. Everything else, this will always re-raise the exception
                    exceptions_dict: {BExampleError: []}
                    raise: AExampleError
                    result: raise


    Args:
        wait_timeout (int): Time in seconds to wait for func to return a value equating to True
        sleep (int): Time in seconds between calls to func
        func (Callable): to be wrapped by TimeoutSampler
        exceptions_dict (ExceptionsDict): Exception handling definition. Keys are exception classes to match
            (using isinstance). Values are lists of filters — strings (matched against str(exception)) or
            callables (invoked with the exception, returning True to ignore/retry). An empty list ignores
            all instances of that exception. See the format example above.
        print_log (bool): Print elapsed time to log.
        print_func_log (bool): Add function call info to log
        print_func_args (bool): Include function arguments in log when print_func_log is True
    """

    def __init__(
        self,
        wait_timeout: float,
        sleep: int,
        func: Callable,
        exceptions_dict: ExceptionsDict | None = None,
        print_log: bool = True,
        print_func_log: bool = True,
        print_func_args: bool = True,
        func_args: tuple[Any] | None = None,
        **func_kwargs: Any,
    ):
        self.wait_timeout = wait_timeout
        self.sleep = sleep
        self.func = func
        self.func_args = func_args or ()
        self.func_kwargs = func_kwargs or {}
        self.print_log = print_log
        self.print_func_log = print_func_log
        self.print_func_args = print_func_args
        self.exceptions_dict = self._validate_exceptions_dict(
            exceptions_dict=exceptions_dict if exceptions_dict is not None else {Exception: []}
        )

    @staticmethod
    def _validate_exceptions_dict(exceptions_dict: ExceptionsDict) -> ExceptionsDict:
        """Validate and return a defensive copy of exceptions_dict.

        Args:
            exceptions_dict (ExceptionsDict): Exception handling definition to validate.

        Returns:
            ExceptionsDict: A validated defensive copy of the input.

        Raises:
            TypeError: If keys aren't Exception subclasses, values aren't lists,
                or filter items aren't strings/callables.
        """
        for key, value in exceptions_dict.items():
            if not isinstance(key, type) or not issubclass(key, Exception):
                raise TypeError(f"exceptions_dict key {key!r} must be an Exception subclass, got {type(key).__name__}")
            if not isinstance(value, list):
                raise TypeError(f"exceptions_dict value for {key.__name__} must be a list, got {type(value).__name__}")
            for filter_item in value:
                if isinstance(filter_item, type):
                    raise TypeError(
                        f"exceptions_dict filter for {key.__name__} contains a class "
                        f"({filter_item.__name__}) instead of a callable or string. "
                        f"Use a lambda (e.g., lambda exc: exc.status >= 500) instead."
                    )
                elif isinstance(filter_item, str) and not filter_item:
                    raise TypeError(
                        f"exceptions_dict filter for {key.__name__} contains an "
                        f"empty string. Use a non-empty substring or a callable instead."
                    )
                elif not isinstance(filter_item, str) and not callable(filter_item):
                    raise TypeError(
                        f"exceptions_dict filter for {key.__name__} contains "
                        f"{type(filter_item).__name__} ({filter_item!r}) — expected str or callable."
                    )
        return {k: list(v) for k, v in exceptions_dict.items()}

    def _get_func_info(self, _func: Callable, type_: str) -> Any:
        # If func is partial function.
        if getattr(_func, "func", None):
            return self._get_func_info(_func=_func.func, type_=type_)  # type: ignore

        res = getattr(_func, type_, None)
        if res:
            # If func is lambda function.
            if _func.__name__ == "<lambda>":
                if type_ == "__module__":
                    return f"{res}.{_func.__qualname__.split('.')[1]}"

                elif type_ == "__name__":
                    free_vars = _func.__code__.co_freevars
                    free_vars_str = f"{'.'.join(free_vars)}." if free_vars else ""
                    return f"lambda: {free_vars_str}{'.'.join(_func.__code__.co_names)}"
            return res

    @property
    def _func_log(self) -> str:
        _func_kwargs = f"Kwargs: {self.func_kwargs}" if (self.print_func_args and self.func_kwargs) else ""
        _func_args = f"Args: {self.func_args}" if (self.print_func_args and self.func_args) else ""
        _func_module = self._get_func_info(_func=self.func, type_="__module__")
        _func_name = self._get_func_info(_func=self.func, type_="__name__")
        return f"Function: {_func_module}.{_func_name} {_func_args} {_func_kwargs}".strip()

    def __iter__(self) -> Any:
        """
        Call `func` and yield the result, or raise an exception on timeout.

        Yields:
            any: Return value from `func`

        Raises:
            TimeoutExpiredError: if `func` takes longer than `wait_timeout` seconds to return a value
        """
        timeout_watch = TimeoutWatch(timeout=self.wait_timeout)
        if self.print_log:
            log = (
                f"Waiting for {self.wait_timeout} seconds"
                f" [{datetime.timedelta(seconds=self.wait_timeout)}], retry every"
                f" {self.sleep} seconds."
            )

            if self.print_func_log:
                log += f" ({self._func_log})"

            LOGGER.info(log)

        last_exp = None
        elapsed_time = None
        while timeout_watch.remaining_time() > 0:
            try:
                elapsed_time = self.wait_timeout - timeout_watch.remaining_time()
                yield self.func(*self.func_args, **self.func_kwargs)
                time.sleep(self.sleep)
                elapsed_time = None

            except Exception as exp:  # noqa: BLE001
                last_exp = exp
                elapsed_time = self.wait_timeout - timeout_watch.remaining_time()

                if not self._should_ignore_exception(exp=last_exp):
                    raise TimeoutExpiredError(
                        self._get_exception_log(exp=last_exp), last_exp=last_exp, elapsed_time=elapsed_time
                    )

                time.sleep(self.sleep)
                elapsed_time = None

            finally:
                if self.print_log and elapsed_time:
                    LOGGER.info(_elapsed_time_log(elapsed_time=elapsed_time))

        raise TimeoutExpiredError(self._get_exception_log(exp=last_exp), last_exp=last_exp)

    @staticmethod
    def _is_exception_matched(exp: Exception, exception_filters: list[ExceptionFilter]) -> bool:
        """
        Verify whether exception should be ignored during retry.

        Args:
            exp (Exception): Exception object raised by `func`
            exception_filters (list): Either an empty list allowing all exceptions,
                a list of strings to match against str(exception),
                or callables that receive the exception and return a truthy value to ignore.
                Callable filters that raise are logged as warnings and treated as non-matching.

        Returns:
            bool: True if exception should be ignored (retry), False otherwise
        """
        if not exception_filters:
            return True

        exp_str: str | None = None
        for filter_item in exception_filters:
            if callable(filter_item):
                try:
                    if filter_item(exp):
                        return True
                except Exception as filter_error:  # noqa: BLE001
                    LOGGER.warning(
                        f"Callable filter {filter_item!r} raised {filter_error!r} "
                        f"for {type(exp).__name__}, treating as non-matching"
                    )
                    continue
            elif isinstance(filter_item, str):
                if exp_str is None:
                    exp_str = str(exp)
                if filter_item in exp_str:
                    return True
        return False

    def _should_ignore_exception(self, exp: Exception) -> bool:
        """
        Verify whether exception should be ignored during execution of `func`

        Args:
            exp (Exception): Exception object raised by `func`

        Returns:
            bool: True if exp should be ignored (retry), False otherwise
        """

        for entry, exception_filters in self.exceptions_dict.items():
            if isinstance(exp, entry) and self._is_exception_matched(exp=exp, exception_filters=exception_filters):
                return True

        return False

    def _get_exception_log(self, exp: Exception | None = None) -> str:
        """
        Get exception log message

        Args:
            exp (any): Raised exception

        Returns:
            str: Log message for exception
        """
        exp_name = exp.__class__.__name__ if exp else "N/A"
        last_exception_log = f"Last exception: {exp_name}"

        if exp:
            last_exception_log += f": {exp}"

        return f"{self.wait_timeout}\n{self._func_log if self.print_func_log else ''}\n{last_exception_log}"


class TimeoutWatch:
    """
    A time counter allowing to determine the time remaining since the start
    of a given interval
    """

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.start_time = time.time()

    def remaining_time(self) -> int | float:
        """
        Return the remaining part of timeout since the object was created.
        """
        _remaining_time = self.start_time + self.timeout - time.time()
        return max(0, _remaining_time)


def retry(
    wait_timeout: int,
    sleep: int,
    exceptions_dict: ExceptionsDict | None = None,
    print_log: bool = True,
    print_func_log: bool = True,
    print_func_args: bool = True,
) -> Callable:
    """
    Decorator for TimeoutSampler, For usage see TimeoutSampler.

    Example:
        from timeout_sampler import retry

        @retry(wait_timeout=1, sleep=1)
        def always_succeeds():
            return True
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: dict[str, Any]) -> Any:
            for sample in TimeoutSampler(
                func=func,
                wait_timeout=wait_timeout,
                sleep=sleep,
                exceptions_dict=exceptions_dict,
                print_log=print_log,
                print_func_log=print_func_log,
                print_func_args=print_func_args,
                func_args=args,
                **kwargs,
            ):
                if sample:
                    return sample

        return wrapper

    return decorator
