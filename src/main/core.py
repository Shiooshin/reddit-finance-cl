"""Core business logic."""

from __future__ import annotations

from main.logger import get_logger

log = get_logger(__name__)


class MyClass:
    """Stub for the primary domain object."""

    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        log.info("greet called for %r", self.name)
        return f"Hello, {self.name}!"


def main() -> None:
    """Entry point for manual smoke-testing."""
    obj = MyClass("worlddd")
    print(obj.greet())


if __name__ == "__main__":
    main()
