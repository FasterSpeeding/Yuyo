# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Copyright (c) 2020-2023, Faster Speeding
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

# pyright: reportUnknownMemberType=none
# This leads to too many false-positives around mocks.

import typing
from collections import abc as collections
from unittest import mock

import pytest

from yuyo import _internal


@pytest.mark.asyncio()
async def test_backwards_compat_aiter_():
    mock_iterable = mock.Mock(
        collections.AsyncIterable,
        __aiter__=mock.Mock(return_value=mock.AsyncMock(collections.AsyncIterator, __anext__=mock.AsyncMock())),
    )

    result: typing.Any = _internal.aiter_(mock_iterable)

    assert result is mock_iterable.__aiter__.return_value
    mock_iterable.__aiter__.assert_called_once_with()


@pytest.mark.asyncio()
async def test_backwards_compat_anext_():
    mock_iterator = mock.Mock(collections.AsyncIterator, __anext__=mock.AsyncMock(return_value=554433))

    assert await _internal.anext_(mock_iterator, 432) == 554433


@pytest.mark.asyncio()
async def test_backwards_compat_anext__when_exhausted():
    mock_iterator = mock.Mock(collections.AsyncIterator, __anext__=mock.AsyncMock(side_effect=StopAsyncIteration))

    assert await _internal.anext_(mock_iterator, 659595) == 659595


@pytest.mark.asyncio()
async def test_backwards_compat_anext__when_exhausted_and_no_default():
    mock_iterator = mock.Mock(collections.AsyncIterator, __anext__=mock.AsyncMock(side_effect=StopAsyncIteration))

    with pytest.raises(StopAsyncIteration):
        await _internal.anext_(mock_iterator)


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("value", "result"),
    [
        (
            mock.Mock(
                collections.AsyncIterable,
                __aiter__=mock.Mock(return_value=mock.Mock(__anext__=mock.AsyncMock(side_effect=[5, 3, 5, 33]))),
            ),
            [5, 3, 5, 33],
        ),
        (
            mock.Mock(
                collections.AsyncIterable,
                __aiter__=mock.Mock(return_value=mock.Mock(__anext__=mock.AsyncMock(side_effect=StopAsyncIteration))),
            ),
            [],
        ),
    ],
)
async def test_collect_iterable_with_async_iterator(value: collections.AsyncIterable[int], result: list[int]):
    assert await _internal.collect_iterable(value) == result


@pytest.mark.asyncio()
@pytest.mark.parametrize(("value", "result"), [(iter((1, 2, 3, 4, 4, 4)), [1, 2, 3, 4, 4, 4]), (iter([]), [])])
async def test_collect_iterable_with_sync_iterator(value: collections.Iterator[int], result: list[int]):
    assert await _internal.collect_iterable(value) == result


@pytest.mark.asyncio()
async def test_seek_iterator_with_async_iterator():
    mock_iterator = mock.Mock(collections.AsyncIterator, __anext__=mock.AsyncMock(return_value=4321234))

    assert await _internal.seek_iterator(mock_iterator, default=123) == 4321234


@pytest.mark.asyncio()
async def test_seek_iterator_with_depleted_async_iterator():
    mock_iterator = mock.Mock(collections.AsyncIterator, __anext__=mock.AsyncMock(side_effect=StopAsyncIteration))

    assert await _internal.seek_iterator(mock_iterator, default=323423) == 323423


@pytest.mark.asyncio()
async def test_seek_iterator_with_sync_iterator():
    mock_iterator = iter([1543, 5, 7, 3, 12])

    assert await _internal.seek_iterator(mock_iterator, default=432) == 1543


@pytest.mark.asyncio()
async def test_seek_iterator_with_depleted_sync_iterator():
    mock_iterator = iter([])

    assert await _internal.seek_iterator(mock_iterator, default=123321) == 123321
