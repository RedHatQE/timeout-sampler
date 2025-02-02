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


# Test raise_on_exceptions
def raise_on_exception():
    raise ValueError()


def raise_on_exception_with_msg():
    raise ValueError("ValueError")


def test_raise_on_exception():
    with pytest.raises(TimeoutExpiredError):
        for sample in TimeoutSampler(
            func=raise_on_exception,
            wait_timeout=2,
            sleep=1,
            raise_on_exceptions={ValueError: []},
            print_log=False,
        ):
            if sample:
                return


def test_raise_on_exception_with_msg():
    with pytest.raises(TimeoutExpiredError):
        for sample in TimeoutSampler(
            func=raise_on_exception_with_msg,
            wait_timeout=2,
            sleep=1,
            raise_on_exceptions={ValueError: ["ValueError"]},
            print_log=False,
        ):
            if sample:
                return


def test_raise_on_exception_with_wrong_msg():
    with pytest.raises(TimeoutExpiredError, match=re.compile(r"Timed Out: 2", re.DOTALL)):
        for sample in TimeoutSampler(
            func=raise_on_exception_with_msg,
            wait_timeout=2,
            sleep=1,
            raise_on_exceptions={ValueError: ["Wrong"]},
            print_log=False,
        ):
            if sample:
                return


def test_raise_on_exception_with_wrong_exception():
    with pytest.raises(TimeoutExpiredError, match=re.compile(r"Timed Out: 2|Last exception: ValueError: ValueError")):
        for sample in TimeoutSampler(
            func=raise_on_exception_with_msg,
            wait_timeout=2,
            sleep=1,
            raise_on_exceptions={TypeError: []},
            print_log=False,
        ):
            if sample:
                return
