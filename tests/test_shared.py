import pytest

from shared.errors import ExternalServiceError
from shared.retry import async_retry


async def test_retry_then_success():
    calls = []

    @async_retry(retries=3, base_delay=0.01, max_delay=0.01)
    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ExternalServiceError("挂了")
        return "ok"

    assert await flaky() == "ok"
    assert len(calls) == 3


async def test_retry_exhausted():
    @async_retry(retries=2, base_delay=0.01, max_delay=0.01)
    async def always_fail():
        raise ExternalServiceError("一直挂")

    with pytest.raises(ExternalServiceError):
        await always_fail()
