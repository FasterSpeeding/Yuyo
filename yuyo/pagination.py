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
"""Utilities used for quick pagination handling within reaction and component executors."""
from __future__ import annotations

__all__: typing.Sequence[str] = ["async_paginate_string", "sync_paginate_string", "paginate_string"]

import collections.abc as collections
import textwrap
import typing

import hikari

T = typing.TypeVar("T")
"""A type hint used to represent the type handled by an iterator."""

DefaultT = typing.TypeVar("DefaultT")
"""A type hint used to represent a "default" argument provided to a function."""


EntryT = typing.Tuple[hikari.UndefinedOr[str], hikari.UndefinedOr[hikari.Embed]]
"""A type hint used to represent a paginator entry.

This should be a tuple of the string message content or `hikari.undefined.UNDEFINED`
to the message's embed if set else `hikari.undefined.UNDEFINED`.
"""

LEFT_DOUBLE_TRIANGLE: typing.Final[hikari.UnicodeEmoji] = hikari.UnicodeEmoji(
    "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to go back to the first entry."""
LEFT_TRIANGLE: typing.Final[hikari.UnicodeEmoji] = hikari.UnicodeEmoji(
    "\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to go back an entry."""
STOP_SQUARE: typing.Final[hikari.UnicodeEmoji] = hikari.UnicodeEmoji(
    "\N{BLACK SQUARE FOR STOP}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to close a menu in a reaction context."""
RIGHT_TRIANGLE: typing.Final[hikari.UnicodeEmoji] = hikari.UnicodeEmoji(
    "\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to continue to the next entry."""
RIGHT_DOUBLE_TRIANGLE: typing.Final[hikari.UnicodeEmoji] = hikari.UnicodeEmoji(
    "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\N{VARIATION SELECTOR-16}"
)
"""The emoji used for the lesser-enabled skip to last entry button."""
BLACK_CROSS: typing.Final[hikari.UnicodeEmoji] = hikari.UnicodeEmoji(
    "\N{HEAVY MULTIPLICATION X}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to close a menu in a component context."""


IteratorT = typing.Union[typing.AsyncIterator[T], typing.Iterator[T]]
"""A type hint used in places where both iterators and async-iterators are supported."""


async def collect_iterator(iterator: IteratorT[T], /) -> typing.List[T]:
    """Collect the rest of an async or sync iterator into a mutable sequence.

    Parameters
    ----------
    iterator : typing.union[typing.AsyncIterator[ValueT], typing.Iterator[ValueT]]
        The iterator to collect. This iterator may be asynchronous or synchronous.

    Returns
    -------
    ValueT
        A sequence of the remaining values in the iterator.
    """
    if isinstance(iterator, collections.AsyncIterator):
        return [value async for value in iterator]

    return list(iterator)


async def seek_iterator(iterator: IteratorT[T], /, default: DefaultT) -> typing.Union[T, DefaultT]:
    """Get the next value in an async or sync iterator."""
    if isinstance(iterator, collections.AsyncIterator):
        return await seek_async_iterator(iterator, default=default)

    return seek_sync_iterator(iterator, default=default)


async def seek_async_iterator(iterator: typing.AsyncIterator[T], /, default: DefaultT) -> typing.Union[T, DefaultT]:
    """Get the next value in an async iterator."""
    async for value in iterator:
        return value

    return default


def seek_sync_iterator(iterator: typing.Iterator[T], /, default: DefaultT) -> typing.Union[T, DefaultT]:
    """Get the next value in an async iterator."""
    return next(iterator, default)


async def async_paginate_string(
    lines: typing.AsyncIterator[str],
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> typing.AsyncIterator[typing.Tuple[str, int]]:
    """Lazily paginate an iterator of lines.

    Parameters
    ----------
    lines : typing.AsyncIterator[builtins.str]
        The asynchronous iterator of lines to paginate.
    char_limit : builtins.int
        The limit for how many characters should be included per yielded page.
        This defaults to 2000
    line_limit : builtins.int
        The limit for how many lines should be included per yielded page.
        This defaults to 25.
    wrapper : typing.Optional[builtins.str]
        A wrapper for each yielded page. This should leave "{}" in it
        to be replaced by the page's content.

    Returns
    -------
    typing.AsyncIterator[typing.Tuple[builtins.str, builtins.int]]
        An async iterator of page tuples (string context to int zero-based index).
    """
    if wrapper:
        char_limit -= len(wrapper) + 2

    # As this is incremented before yielding and zero-index we have to start at -1.
    page_number = -1
    page_size = 0
    page: typing.List[str] = []

    while (line := await seek_async_iterator(lines, default=None)) is not None:
        # If the page is already populated and adding the current line would bring it over one of the predefined limits
        # then we want to yield this page.
        if len(page) >= line_limit or page and page_size + len(line) > char_limit:
            yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page), (page_number := page_number + 1)
            page.clear()
            page_size = 0

        # If the current line doesn't fit into a page then we need to split it up into sub-pages to yield and can
        # assume the previous page was yielded.
        if len(line) >= char_limit:
            sub_pages = textwrap.wrap(
                line, width=char_limit, drop_whitespace=False, break_on_hyphens=False, expand_tabs=False
            )

            # If the last page could possible fit into a page with other lines then we add it to the next page
            # to avoid sending small terraced pages.
            if len(sub_pages[-1]) < char_limit:
                sub_line = sub_pages.pop(-1)
                page_size += len(sub_line)
                page.append(sub_line)

            # yield all the sub-lines at once.
            for sub_line in map(wrapper.format, sub_pages) if wrapper else sub_pages:
                yield sub_line, (page_number := page_number + 1)

        # Otherwise it should be added to the next page.
        else:
            page_size += len(line)
            page.append(line)

    # This catches the likely dangling page after iteration ends.
    if page:
        yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page), page_number + 1


def sync_paginate_string(
    lines: typing.Iterator[str],
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> typing.Iterator[typing.Tuple[str, int]]:
    """Lazily paginate an iterator of lines.

    Parameters
    ----------
    lines : typing.Iterator[builtins.str]
        The iterator of lines to paginate.
    char_limit : builtins.int
        The limit for how many characters should be included per yielded page.
        This defaults to 2000
    line_limit : builtins.int
        The limit for how many lines should be included per yielded page.
        This defaults to 25.
    wrapper : typing.Optional[builtins.str]
        A wrapper for each yielded page. This should leave "{}" in it
        to be replaced by the page's content.

    Returns
    -------
    typing.Iterator[typing.Tuple[builtins.str, builtins.int]]
        An iterator of page tuples (string context to int zero-based index).
    """
    if wrapper:
        char_limit -= len(wrapper) + 2

    # As this is incremented before yielding and zero-index we have to start at -1.
    page_number = -1
    page_size = 0
    page: typing.List[str] = []

    while (line := seek_sync_iterator(lines, default=None)) is not None:
        # If the page is already populated and adding the current line would bring it over one of the predefined limits
        # then we want to yield this page.
        if len(page) >= line_limit or page and page_size + len(line) > char_limit:
            yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page), (page_number := page_number + 1)
            page.clear()
            page_size = 0

        # If the current line doesn't fit into a page then we need to split it up into sub-pages to yield and can
        # assume the previous page was yielded.
        if len(line) >= char_limit:
            sub_pages = textwrap.wrap(
                line, width=char_limit, drop_whitespace=False, break_on_hyphens=False, expand_tabs=False
            )

            # If the last page could possible fit into a page with other lines then we add it to the next page
            # to avoid sending small terraced pages.
            if len(sub_pages[-1]) < char_limit:
                sub_line = sub_pages.pop(-1)
                page_size += len(sub_line)
                page.append(sub_line)

            # yield all the sub-lines at once.
            for sub_line in map(wrapper.format, sub_pages) if wrapper else sub_pages:
                yield sub_line, (page_number := page_number + 1)

        # Otherwise it should be added to the next page.
        else:
            page_size += len(line)
            page.append(line)

    # This catches the likely dangling page after iteration ends.
    if page:
        yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page), page_number + 1


@typing.overload
def paginate_string(
    lines: typing.AsyncIterator[str],
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> typing.AsyncIterator[typing.Tuple[str, int]]:
    ...


@typing.overload
def paginate_string(
    lines: typing.Iterator[str],
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> typing.Iterator[typing.Tuple[str, int]]:
    ...


def paginate_string(
    lines: IteratorT[str],
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> IteratorT[typing.Tuple[str, int]]:
    """Lazily paginate an iterator of lines.

    Parameters
    ----------
    lines : typing.union[typing.AsyncIterator[builtins.str], typing.Iterator[builtins.str]]
        The iterator of lines to paginate. This iterator may be asynchronous or synchronous.
    char_limit : builtins.int
        The limit for how many characters should be included per yielded page.
        This defaults to 2000
    line_limit : builtins.int
        The limit for how many lines should be included per yielded page.
        This defaults to 25.
    wrapper : typing.Optional[builtins.str]
        A wrapper for each yielded page. This should leave "{}" in it
        to be replaced by the page's content.

    Returns
    -------
    typing.Union[AsyncIterator[typing.Tuple[builtins.str, builtins.int]], typing.Iterator[typing.Tuple[builtins.str, builtins.int]]]
        An iterator of page tuples (string context to int zero-based index).
    """  # noqa: E501  - line too long
    if isinstance(lines, typing.AsyncIterator):
        return async_paginate_string(lines, char_limit=char_limit, line_limit=line_limit, wrapper=wrapper)

    return sync_paginate_string(lines, char_limit=char_limit, line_limit=line_limit, wrapper=wrapper)
