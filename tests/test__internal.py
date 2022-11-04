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

import typing
from collections import abc as collections
from unittest import mock

# pyright: reportUnknownMemberType=none
# This leads to too many false-positives around mocks.
import pytest

from yuyo import _internal


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("value", "result"),
    [
        (
            mock.Mock(
                collections.AsyncIterator,
                __aiter__=mock.Mock(return_value=mock.Mock(__anext__=mock.AsyncMock(side_effect=[5, 3, 5, 33]))),
            ),
            [5, 3, 5, 33],
        ),
        (
            mock.Mock(
                collections.AsyncIterator,
                __aiter__=mock.Mock(return_value=mock.Mock(__anext__=mock.AsyncMock(side_effect=StopAsyncIteration))),
            ),
            [],
        ),
    ],
)
async def test_collect_iterable_with_async_iterator(value: typing.AsyncIterator[int], result: typing.List[int]):
    assert await _internal.collect_iterable(value) == result


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("value", "result"),
    [
        (iter((1, 2, 3, 4, 4, 4)), [1, 2, 3, 4, 4, 4]),
        (iter([]), []),
    ],
)
async def test_collect_iterable_with_sync_iterator(value: typing.Iterator[int], result: typing.List[int]):
    assert await _internal.collect_iterable(value) == result


@pytest.mark.asyncio()
async def test_seek_iterator_with_async_iterator():
    mock_iterator = mock.Mock(collections.AsyncIterator)

    with mock.patch.object(_internal, "seek_async_iterator") as seek_async_iterator:
        assert await _internal.seek_iterator(mock_iterator, default=123) is seek_async_iterator.return_value

        seek_async_iterator.assert_awaited_once_with(mock_iterator, default=123)


@pytest.mark.asyncio()
async def test_seek_iterator_with_sync_iterator():
    mock_iterator = mock.Mock(collections.Iterator)

    with mock.patch.object(_internal, "seek_sync_iterator") as seek_sync_iterator:
        assert await _internal.seek_iterator(mock_iterator, default=432) is seek_sync_iterator.return_value

        seek_sync_iterator.assert_called_once_with(mock_iterator, default=432)


@pytest.mark.asyncio()
async def test_seek_async_iterator():
    mock_iterator = mock.Mock(
        collections.AsyncIterator,
        __aiter__=mock.Mock(return_value=mock.Mock(__anext__=mock.AsyncMock(return_value=554433))),
    )

    assert await _internal.seek_async_iterator(mock_iterator, default=432) == 554433


@pytest.mark.asyncio()
async def test_seek_async_iterator_when_exhausted():
    mock_iterator = mock.Mock(
        collections.AsyncIterator,
        __aiter__=mock.Mock(return_value=mock.Mock(__anext__=mock.AsyncMock(side_effect=StopAsyncIteration))),
    )

    assert await _internal.seek_async_iterator(mock_iterator, default=659595) == 659595


def test_seek_sync_iterator():
    assert _internal.seek_sync_iterator(iter((1,)), default=3322232) == 1


def test_seek_sync_iterator_when_exhausted():
    assert _internal.seek_sync_iterator(iter(()), default=3322232) == 3322232
