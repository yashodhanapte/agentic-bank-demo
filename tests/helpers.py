"""Shared test helpers: scripted fake API responses and a fake client."""

from types import SimpleNamespace as NS


# ---- helpers: build fake API responses -------------------------------------
def text(t):
    return NS(type="text", text=t)


def tool_use(id, name, **inputs):
    return NS(type="tool_use", id=id, name=name, input=inputs)


def reply(blocks, stop="end_turn", tin=10, tout=5):
    return NS(
        content=blocks,
        stop_reason=stop,
        usage=NS(input_tokens=tin, output_tokens=tout),
    )


class FakeClient:
    """Hands back scripted replies in order and records every call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = self  # so client.messages.create(...) works

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.replies.pop(0)
