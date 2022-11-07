import typing

from typing_extensions import Self

_FooT = typing.TypeVar("_FooT", bound="Foo")


class Barist(typing.Protocol):
    def foo(self, callback: typing.Callable[["Barist"], None]) -> None:
        raise NotImplementedError

    def bar(self, value: int) -> int:
        raise NotImplementedError


class Foo:
    def foo(self, callback: typing.Callable[[Self], None]) -> None:
        return None


class Bar(Foo):
    def bar(self, value: int) -> int:
        return ~value


if typing.TYPE_CHECKING:

    def _foo(_: Barist) -> None:
        return None

    def _bar(value: Bar) -> None:  # pyright: ignore [ reportUnusedFunction ]
        _foo(value)
