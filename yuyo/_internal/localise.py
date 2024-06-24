# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Copyright (c) 2020-2024, Faster Speeding
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""A collection of utility functions and classes designed to expand Hikari."""
from __future__ import annotations

__all__: list[str] = ["MaybeLocalised", "MaybeLocalsiedType"]

import typing
from collections import abc as collections

if typing.TYPE_CHECKING:
    import hikari
    from typing_extensions import Self

    from .. import interactions

_T = typing.TypeVar("_T", bound=object)

MaybeLocalsiedType = typing.Union[_T, collections.Mapping[str, _T]]


class MaybeLocalised(typing.Generic[_T]):
    """Helper class used for handling localisation."""

    __slots__ = ("field_name", "value", "localisations")

    def __init__(self, field_name: str, value: _T, localisations: collections.Mapping[str, _T]) -> None:
        self.field_name = field_name
        self.value = value
        self.localisations = localisations

    @classmethod
    def parse(cls, field_name: typing.Union[str, hikari.Locale], raw_value: MaybeLocalsiedType[_T], /) -> Self:
        if isinstance(raw_value, collections.Mapping):
            raw_value = typing.cast("collections.Mapping[str, _T]", raw_value)
            value = raw_value.get("default") or next(iter(raw_value.values()))
            localisations: dict[str, _T] = {k: v for k, v in raw_value.items() if k != "default"}
            return cls(field_name, value, localisations)

        return cls(field_name, raw_value, {})

    def _values(self) -> collections.Iterable[_T]:
        yield self.value
        yield from self.localisations.values()

    def assert_matches(self, pattern: str, match: collections.Callable[[_T], bool], /) -> Self:
        for value in self._values():
            if not match(value):
                raise ValueError(
                    f"Invalid {self.field_name} provided, {value!r} doesn't match the required pattern `{pattern}`"
                )

        return self

    def localise(
        self,
        ctx: typing.Union[
            interactions.BaseContext[hikari.ComponentInteraction], interactions.BaseContext[hikari.ModalInteraction]
        ],
        /,
    ) -> _T:
        return self.localisations.get(ctx.interaction.locale) or self.value
