# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020-2022, Faster Speeding
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

__all__: typing.Sequence[str] = []

import sys
import typing
from collections import abc as collections

_T = typing.TypeVar("_T")
_DefaultT = typing.TypeVar("_DefaultT")
IterableT = typing.Union[typing.AsyncIterable[_T], typing.Iterable[_T]]
IteratorT = typing.Union[typing.AsyncIterator[_T], typing.Iterator[_T]]

_NO_DEFAULT = object()


if sys.version_info >= (3, 10):
    aiter_ = aiter  # noqa: F821
    anext_ = anext  # noqa: F821

else:

    def aiter_(iterable: typing.AsyncIterable[_T], /) -> typing.AsyncIterator[_T]:
        """Backwards compat impl of `aiter`."""
        return iterable.__aiter__()

    @typing.overload
    async def anext_(iterator: typing.AsyncIterator[_T], /) -> _T:
        ...

    @typing.overload
    async def anext_(iterator: typing.AsyncIterator[_T], default: _DefaultT, /) -> typing.Union[_T, _DefaultT]:
        ...

    async def anext_(
        iterator: typing.AsyncIterator[_T], default: _DefaultT = _NO_DEFAULT, /
    ) -> typing.Union[_T, _DefaultT]:
        """Backwards compat impl of `anext`."""
        try:
            return await iterator.__anext__()
        except StopAsyncIteration:
            if default is _NO_DEFAULT:
                raise

            return typing.cast("_T", default)


async def collect_iterable(iterator: IterableT[_T], /) -> typing.List[_T]:
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


async def seek_iterator(iterator: IteratorT[_T], /, default: _DefaultT) -> typing.Union[_T, _DefaultT]:
    """Get the next value in an async or sync iterator."""
    if isinstance(iterator, collections.AsyncIterator):
        return await anext_(iterator, default)

    return next(iterator, default)
