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

import hikari
import pytest

from yuyo import _internal
from yuyo import pagination

_T = typing.TypeVar("_T")


@pytest.mark.skip()
async def test_async_paginate_string():
    raise NotImplementedError


@pytest.mark.skip()
def test_sync_paginate_string():
    raise NotImplementedError


def test_paginate_string_with_async_iterator():
    mock_iterator = mock.Mock(collections.AsyncIterator, __aiter__=mock.Mock(), __anext__=mock.Mock())

    with mock.patch.object(pagination, "async_paginate_string") as async_paginate_string:
        result = pagination.paginate_string(mock_iterator, char_limit=432, line_limit=563, wrapper="sex me")

        assert result is async_paginate_string.return_value
        async_paginate_string.assert_called_once_with(mock_iterator, char_limit=432, line_limit=563, wrapper="sex me")


def test_paginate_string_with_sync_iterator():
    mock_iterator = iter(("1", "2", "3"))

    with mock.patch.object(pagination, "sync_paginate_string") as sync_paginate_string:
        result = pagination.paginate_string(mock_iterator, char_limit=222, line_limit=5555, wrapper="s")

        assert result is sync_paginate_string.return_value
        sync_paginate_string.assert_called_once_with(mock_iterator, char_limit=222, line_limit=5555, wrapper="s")


async def fake_awake(value: _T, /) -> _T:
    return value


@pytest.mark.asyncio()
async def test_aenumerate():
    iterator = pagination.aenumerate((await fake_awake(value) for value in ("a", "meow", "nyaa", "nom")))

    result = await _internal.collect_iterable(iterator)

    assert result == [(0, "a"), (1, "meow"), (2, "nyaa"), (3, "nom")]


@pytest.mark.asyncio()
async def test_aenumerate_for_empty_iterator():
    raw_iterator = (await fake_awake(value) for value in iter(()))
    iterator = pagination.aenumerate(raw_iterator)

    result = await _internal.collect_iterable(iterator)

    assert result == []


class TestPage:
    def test_from_entry(self):
        original_page = pagination.Page(content="a", attachments=[mock.Mock()], embeds=[mock.Mock()])

        page = pagination.Page.from_entry(original_page)

        assert page is original_page

    def test_from_entry_when_tuple(self):
        mock_embed = mock.Mock()

        page = pagination.Page.from_entry(("meow", mock_embed))

        assert page.to_kwargs() == {"attachments": hikari.UNDEFINED, "content": "meow", "embeds": [mock_embed]}

    def test_from_entry_when_tuple_and_both_undefined(self):
        page = pagination.Page.from_entry((hikari.UNDEFINED, hikari.UNDEFINED))

        assert page.to_kwargs() == {
            "attachments": hikari.UNDEFINED,
            "content": hikari.UNDEFINED,
            "embeds": hikari.UNDEFINED,
        }

    def test_from_entry_when_tuple_and_content_undefined(self):
        mock_embed = mock.Mock()

        page = pagination.Page.from_entry((hikari.UNDEFINED, mock_embed))

        assert page.to_kwargs() == {
            "attachments": hikari.UNDEFINED,
            "content": hikari.UNDEFINED,
            "embeds": [mock_embed],
        }

    def test_from_entry_when_tuple_and_embed_undefined(self):
        page = pagination.Page.from_entry(("very special content", hikari.UNDEFINED))

        assert page.to_kwargs() == {
            "attachments": hikari.UNDEFINED,
            "content": "very special content",
            "embeds": hikari.UNDEFINED,
        }

    def test_to_kwargs(self):
        mock_attachment_1 = mock.Mock()
        mock_attachment_2 = mock.Mock()
        mock_embed_1 = mock.Mock()
        mock_embed_2 = mock.Mock()
        page = pagination.Page(
            content="himeowmeow",
            attachments=[mock_attachment_1, mock_attachment_2],
            embeds=[mock_embed_1, mock_embed_2],
        )

        result = page.to_kwargs()

        assert result == {
            "content": "himeowmeow",
            "attachments": [mock_attachment_1, mock_attachment_2],
            "embeds": [mock_embed_1, mock_embed_2],
        }

    def test_to_kwargs_when_all_undefined(self):
        result = pagination.Page().to_kwargs()

        assert result == {"attachments": hikari.UNDEFINED, "content": hikari.UNDEFINED, "embeds": hikari.UNDEFINED}
