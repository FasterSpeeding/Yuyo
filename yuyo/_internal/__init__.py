# BSD 3-Clause License
#
# Copyright (c) 2020-2025, Faster Speeding
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
"""Internal functions and types used in Yuyo."""
from __future__ import annotations

__all__: list[str] = []

import enum
import typing
import uuid
from collections import abc as collections

import hikari

if typing.TYPE_CHECKING:
    _DefaultT = typing.TypeVar("_DefaultT")
    _OtherT = typing.TypeVar("_OtherT")

_T = typing.TypeVar("_T")
IterableT = collections.AsyncIterable[_T] | collections.Iterable[_T]
IteratorT = collections.AsyncIterator[_T] | collections.Iterator[_T]


class GatewayBotProto(hikari.EventManagerAware, hikari.RESTAware, hikari.ShardAware, typing.Protocol):
    """Protocol of a cacheless Hikari Gateway bot."""


class _NoDefaultEnum(enum.Enum):
    VALUE = object()


NO_DEFAULT = _NoDefaultEnum.VALUE
"""Internal singleton used to signify when a value wasn't provided."""

NoDefault = typing.Literal[_NoDefaultEnum.VALUE]
"""The type of `NO_DEFAULT`."""


async def collect_iterable(iterator: IterableT[_T], /) -> list[_T]:
    """Collect the rest of an async or sync iterator into a mutable sequence.

    Parameters
    ----------
    iterator
        The iterator to collect. This iterator may be asynchronous or synchronous.

    Returns
    -------
    list[T]
        A sequence of the remaining values in the iterator.
    """
    if isinstance(iterator, collections.AsyncIterable):
        return [value async for value in iterator]

    return list(iterator)


async def seek_iterator(iterator: IteratorT[_T], /, default: _DefaultT) -> _T | _DefaultT:
    """Get the next value in an async or sync iterator."""
    if isinstance(iterator, collections.AsyncIterator):
        return await anext(iterator, default)

    return next(iterator, default)


def random_custom_id() -> str:
    """Generate a random custom ID."""
    return uuid.uuid4().hex


class SplitId(typing.NamedTuple):
    """Represents a split custom ID."""

    id_match: str
    id_metadata: str


def split_custom_id(custom_id: str) -> SplitId:
    """Split a custom ID into its match and metadata parts.

    Returns
    -------
    tuple[str, str]
        Tuple of the ID's match part and the ID's metadata part.
    """
    parts = custom_id.split(":", 1)

    try:
        id_metadata = parts[1]

    except IndexError:
        id_metadata = ""

    return SplitId(id_match=parts[0], id_metadata=id_metadata)


class MatchId(typing.NamedTuple):
    """Represents a generated match ID and the relevant full custom ID."""

    id_match: str
    custom_id: str


def gen_custom_id(custom_id: str | None) -> MatchId:
    """Generate a custom ID from user input.

    Returns
    -------
    tuple[str, str]
        Tuple of the ID's match part and the full custom ID.
    """
    if custom_id is None:
        custom_id = random_custom_id()
        return MatchId(custom_id, custom_id)

    return MatchId(id_match=split_custom_id(custom_id).id_match, custom_id=custom_id)


def to_list(
    singular: hikari.UndefinedOr[_T],
    plural: hikari.UndefinedOr[collections.Sequence[_T]],
    other: _OtherT,
    type_: type[_T] | tuple[type[_T], ...],
    name: str,
    /,
) -> tuple[hikari.UndefinedOr[list[_T]], hikari.UndefinedOr[_OtherT]]:
    """Convert Hikari create/edit message kwargs to a list."""
    if singular is not hikari.UNDEFINED and plural is not hikari.UNDEFINED:
        error_message = f"Only one of {name} or {name}s may be passed"
        raise ValueError(error_message)

    if singular is not hikari.UNDEFINED:
        return [singular], other

    if plural is not hikari.UNDEFINED:
        return list(plural), other

    if other and isinstance(other, type_):
        return [other], hikari.UNDEFINED

    return hikari.UNDEFINED, other
