"""Deterministic monotonic + sleep for clock-write tests.

Lives outside conftest on purpose: importing conftest as a module re-executes
it, which reinstalls the Home Assistant stubs in sys.modules and quietly
replaces exception classes the already-imported code is matching against.
"""

from __future__ import annotations


class StubClock:
    """Monotonic reading plus a sleep that only advances it.

    ``set_time`` holds its write back until a second boundary; without this the
    suite would spend a real second per clock write proving nothing.
    """

    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    async def sleep(self, seconds: float) -> None:
        self.t += seconds

    @property
    def hooks(self) -> dict:
        """Keyword arguments for set_time / set_time_format."""
        return {"monotonic": self, "sleeper": self.sleep}
