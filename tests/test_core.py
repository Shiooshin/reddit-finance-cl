"""Tests for main.core."""

from main.core import MyClass


class TestMyClass:
    def test_greet_returns_expected_string(self) -> None:
        obj = MyClass("world")
        assert obj.greet() == "Hello, world!"

    def test_name_stored(self) -> None:
        obj = MyClass("Alice")
        assert obj.name == "Alice"
