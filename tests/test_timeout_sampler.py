import re

import pytest

from timeout_sampler import TimeoutExpiredError, TimeoutSampler, retry


class TestTimeoutSampler:
    @staticmethod
    def _raise_exception(runtime_exception):
        if runtime_exception:
            raise runtime_exception

    def _trigger_func_exception_during_iter(self, exceptions_dict, runtime_exception):
        for _ in TimeoutSampler(
            wait_timeout=1,
            sleep=1,
            func=self._raise_exception,
            exceptions_dict=exceptions_dict,
            print_log=False,
            runtime_exception=runtime_exception,
        ):
            continue

    @pytest.mark.parametrize(
        "test_params",
        [
            pytest.param(
                {
                    "init_exceptions_dict": {
                        KeyError: [],
                    },
                    "runtime_exception": ValueError(),
                },
                id="init_keyerror_raise_valueerror_with_no_msg",
            ),
            pytest.param(
                {
                    "init_exceptions_dict": {},
                    "runtime_exception": ValueError(),
                },
                id="init_any_exception_raise_valueerror_with_no_msg",
            ),
            pytest.param(
                {
                    "init_exceptions_dict": {
                        ValueError: ["allowed exception text"],
                    },
                    "runtime_exception": ValueError("test"),
                },
                id="init_valueerror_with_msg_raise_valueerror_with_invalid_msg",
            ),
            pytest.param(
                {
                    "init_exceptions_dict": {
                        KeyError: ["allowed exception text"],
                        IndexError: ["allowed exception text"],
                        ValueError: ["allowed exception text"],
                    },
                    "runtime_exception": IndexError("test"),
                },
                id="init_multi_exceptions_raise_allowed_with_invalid_msg",
            ),
        ],
    )
    def test_timeout_sampler_raises(self, test_params):
        with pytest.raises(TimeoutExpiredError):
            self._trigger_func_exception_during_iter(
                exceptions_dict=test_params.get("init_exceptions_dict"),
                runtime_exception=test_params.get("runtime_exception"),
            )

    @pytest.mark.parametrize(
        "test_params, expected",
        [
            pytest.param(
                {},
                {
                    "exception_log_regex": "^.*\nLast exception: N/A",
                },
                id="noargs_timeout_only",
            ),
            pytest.param(
                {
                    "runtime_exception": Exception(),
                },
                {
                    "exception_log_regex": "^.*\nLast exception: Exception:",
                },
                id="noargs_raise_exception_with_no_msg",
            ),
            pytest.param(
                {
                    "runtime_exception": ValueError(),
                },
                {
                    "exception_log_regex": "^.*\nLast exception: ValueError:",
                },
                id="noargs_raise_valueerror_with_no_msg",
            ),
            pytest.param(
                {
                    "init_exceptions_dict": {
                        ValueError: ["test"],
                    },
                    "runtime_exception": ValueError("test"),
                },
                {
                    "exception_log_regex": "^.*\nLast exception: ValueError: test",
                },
                id="init_valueerror_with_msg_raise_valueerror_with_allowed_msg",
            ),
            pytest.param(
                {
                    "init_exceptions_dict": {
                        KeyError: ["allowed exception text"],
                        IndexError: ["allowed exception text"],
                        ValueError: ["allowed exception text"],
                    },
                    "runtime_exception": IndexError("my allowed exception text"),
                },
                {
                    "exception_log_regex": ("^.*\nLast exception: IndexError: my allowed exception text"),
                },
                id="init_multi_exceptions_raise_allowed_with_allowed_msg",
            ),
        ],
    )
    def test_timeout_sampler_raises_timeout(self, test_params, expected):
        exception_match = None
        exception_log = None
        try:
            self._trigger_func_exception_during_iter(
                exceptions_dict=test_params.get("init_exceptions_dict"),
                runtime_exception=test_params.get("runtime_exception"),
            )
        except TimeoutExpiredError as exp:
            exception_log = str(exp)
            exception_match = re.compile(pattern=expected["exception_log_regex"], flags=re.DOTALL).match(
                string=exception_log
            )

        assert exception_match, f"Expected Regex: {expected['exception_log_regex']!r} Exception Log: {exception_log!r}"


def test_sampler():
    sampler = TimeoutSampler(wait_timeout=1, sleep=1, print_log=False, func=lambda: True)
    for sample in sampler:
        if sample:
            return

    pytest.fail("Sampler rise timeout")


def test_sampler_negative():
    sampler = TimeoutSampler(
        wait_timeout=10,
        sleep=1,
        func=lambda: False,
        print_log=False,
    )
    with pytest.raises(TimeoutExpiredError):
        for sample in sampler:
            if sample:
                return


# retry decorator tests


@retry(
    wait_timeout=1,
    sleep=1,
    print_log=False,
)
def always_succeeds():
    return True


@retry(
    wait_timeout=1,
    sleep=1,
    print_log=False,
)
def never_succeeds():
    return False


def test_decorator():
    always_succeeds()


def test_decorator_negative():
    with pytest.raises(TimeoutExpiredError):
        never_succeeds()


# callable filter tests


class StatusError(Exception):
    """Exception with a status attribute for testing callable filters."""

    def __init__(self, status: int):
        self.status = status
        super().__init__(f"{status}")


class TestCallableExceptionFilter:
    @staticmethod
    def _raise_status_error(status: int):
        raise StatusError(status=status)

    def test_callable_filter_ignores_matching_exception(self):
        """Callable returning True should ignore the exception and allow retry."""
        with pytest.raises(TimeoutExpiredError):
            for _ in TimeoutSampler(
                wait_timeout=1,
                sleep=1,
                func=self._raise_status_error,
                exceptions_dict={StatusError: [lambda exc: exc.status >= 500]},
                print_log=False,
                status=502,
            ):
                continue

    def test_callable_filter_raises_non_matching_exception(self):
        """Callable returning False should re-raise the exception immediately."""
        with pytest.raises(TimeoutExpiredError) as exc_info:
            for _ in TimeoutSampler(
                wait_timeout=1,
                sleep=1,
                func=self._raise_status_error,
                exceptions_dict={StatusError: [lambda exc: exc.status >= 500]},
                print_log=False,
                status=400,
            ):
                continue
        assert exc_info.value.last_exp is not None
        assert exc_info.value.last_exp.status == 400

    def test_callable_filter_with_string_filter_combined(self):
        """Callable and string filters can coexist in the same list."""
        with pytest.raises(TimeoutExpiredError):
            for _ in TimeoutSampler(
                wait_timeout=1,
                sleep=1,
                func=self._raise_status_error,
                exceptions_dict={StatusError: ["999", lambda exc: exc.status >= 500]},
                print_log=False,
                status=503,
            ):
                continue

    def test_string_filter_still_works(self):
        """Existing string matching behavior is unchanged."""
        with pytest.raises(TimeoutExpiredError):
            for _ in TimeoutSampler(
                wait_timeout=1,
                sleep=1,
                func=self._raise_status_error,
                exceptions_dict={StatusError: ["502"]},
                print_log=False,
                status=502,
            ):
                continue

    def test_empty_list_still_matches_all(self):
        """Empty list continues to match all exceptions of the given type."""
        with pytest.raises(TimeoutExpiredError):
            for _ in TimeoutSampler(
                wait_timeout=1,
                sleep=1,
                func=self._raise_status_error,
                exceptions_dict={StatusError: []},
                print_log=False,
                status=400,
            ):
                continue
