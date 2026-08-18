import pytest

from qa_api.generator.llm import stream_answer
from shared.errors import ExternalServiceError


class FakeStream:
    def __init__(self, deltas):
        self._deltas = iter(deltas)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._deltas)
        except StopIteration:
            raise StopAsyncIteration


class FakeChat:
    def __init__(self, stream):
        self._stream = stream
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        return self._stream()


class FakeCompletions:
    def __init__(self, chat):
        # 与真实 OpenAI SDK 结构对齐：client.chat.completions.create(...)
        self.completions = chat


class FakeLLM:
    def __init__(self, stream):
        self.chat = FakeCompletions(FakeChat(stream))


class BrokenLLM(FakeLLM):
    def __init__(self):
        super().__init__(self._boom)

    def _boom(self):
        raise RuntimeError("primary down")


def chunk(delta):
    return type("C", (), {"choices": [type("Ch", (), {"delta": type("D", (), {"content": delta})()})()]})()


async def test_primary_fails_backup_used():
    primary = BrokenLLM()
    backup = FakeLLM(lambda: FakeStream([chunk("从"), chunk("备"), chunk("用")]))
    out = []
    async for delta in stream_answer("放假时间？", "ctx", llm=primary, backup=backup):
        out.append(delta)
    assert "".join(out) == "从备用"
    assert backup.chat.completions.calls == 1


async def test_both_fail_raises():
    primary = BrokenLLM()
    backup = BrokenLLM()
    with pytest.raises(ExternalServiceError):
        async for _ in stream_answer("放假时间？", "ctx", llm=primary, backup=backup):
            pass
