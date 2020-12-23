from __future__ import annotations

__all__: typing.Sequence[str] = ["try_find_type"]

import typing

_T = typing.TypeVar("_T")


def try_find_type(cls: typing.Type[_T], *values: typing.Any) -> typing.Optional[_T]:
    for value in values:
        if isinstance(value, cls):
            return value

    return None
