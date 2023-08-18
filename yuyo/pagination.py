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
"""Utilities used for quick pagination handling within reaction and component executors."""
from __future__ import annotations

__all__: list[str] = ["Page", "aenumerate", "async_paginate_string", "paginate_string", "sync_paginate_string"]

import textwrap
import typing
from collections import abc as collections

import hikari

from . import _internal

if typing.TYPE_CHECKING:
    _T = typing.TypeVar("_T")

    class _ResponseKwargs(typing.TypedDict):
        content: hikari.UndefinedOr[str]
        attachments: hikari.UndefinedOr[collections.Sequence[hikari.Resourceish]]
        embeds: hikari.UndefinedOr[collections.Sequence[hikari.Embed]]


EntryT = typing.Union[tuple[hikari.UndefinedOr[str], hikari.UndefinedOr[hikari.Embed]], "Page"]
"""A type hint used to represent a paginator entry.

This may be either [Page][yuyo.pagination.Page] or
`tuple[hikari.UndefinedOr[str], hikari.UndefinedOr[hikari.Embed]]` where tuple[0]
is the message content and tuple[1] is an embed to send.
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
"""The emoji used for the (not enabled by default) skip to last entry button."""

BLACK_CROSS: typing.Final[hikari.UnicodeEmoji] = hikari.UnicodeEmoji(
    "\N{HEAVY MULTIPLICATION X}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to close a menu in a component context."""


async def async_paginate_string(
    lines: collections.AsyncIterable[str],
    /,
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> collections.AsyncIterator[str]:
    """Lazily paginate an iterator of lines.

    Parameters
    ----------
    lines
        The asynchronous iterator of lines to paginate.
    char_limit
        The limit for how many characters should be included per yielded page.
    line_limit
        The limit for how many lines should be included per yielded page.
    wrapper
        A wrapper for each yielded page. This should leave "{}" in it
        to be replaced by the page's content.

    Returns
    -------
    collections.abc.AsyncIterator[str]
        An async iterator of each page's content.
    """
    if wrapper:
        char_limit -= len(wrapper) + 2

    # As this is incremented before yielding and zero-index we have to start at -1.
    page_size = 0
    page: list[str] = []
    lines = _internal.aiter_(lines)

    while (line := await _internal.anext_(lines, None)) is not None:
        # If the page is already populated and adding the current line would bring it over one of the predefined limits
        # then we want to yield this page.
        if len(page) >= line_limit or page and page_size + len(line) > char_limit:
            yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page)
            page.clear()
            page_size = 0

        # If the current line doesn't fit into a page then we need to split it up into sub-pages to yield and can
        # assume the previous page was yielded.
        if len(line) >= char_limit:
            sub_pages = textwrap.wrap(
                line, width=char_limit, drop_whitespace=False, break_on_hyphens=False, expand_tabs=False
            )

            # If the last page could possibly fit into a page with other lines then we add it to the next page
            # to avoid sending small terraced pages.
            if len(sub_pages[-1]) < char_limit:
                sub_line = sub_pages.pop(-1)
                page_size += len(sub_line)
                page.append(sub_line)

            # yield all the sub-lines at once.
            for sub_line in map(wrapper.format, sub_pages) if wrapper else sub_pages:
                yield sub_line

        # Otherwise it should be added to the next page.
        else:
            page_size += len(line)
            page.append(line)

    # This catches the likely dangling page after iteration ends.
    if page:
        yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page)


def sync_paginate_string(
    lines: collections.Iterable[str],
    /,
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> collections.Iterator[str]:
    """Lazily paginate an iterator of lines.

    Parameters
    ----------
    lines
        The iterator of lines to paginate.
    char_limit
        The limit for how many characters should be included per yielded page.
    line_limit
        The limit for how many lines should be included per yielded page.
    wrapper
        A wrapper for each yielded page. This should leave "{}" in it
        to be replaced by the page's content.

    Returns
    -------
    collections.abc.Iterator[str]
        An iterator of each page's content.
    """
    if wrapper:
        char_limit -= len(wrapper) + 2

    # As this is incremented before yielding and zero-index we have to start at -1.
    page_size = 0
    page: list[str] = []
    lines = iter(lines)

    while (line := next(lines, None)) is not None:
        # If the page is already populated and adding the current line would bring it over one of the predefined limits
        # then we want to yield this page.
        if len(page) >= line_limit or page and page_size + len(line) > char_limit:
            yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page)
            page.clear()
            page_size = 0

        # If the current line doesn't fit into a page then we need to split it up into sub-pages to yield and can
        # assume the previous page was yielded.
        if len(line) >= char_limit:
            sub_pages = textwrap.wrap(
                line, width=char_limit, drop_whitespace=False, break_on_hyphens=False, expand_tabs=False
            )

            # If the last page could possibly fit into a page with other lines then we add it to the next page
            # to avoid sending small terraced pages.
            if len(sub_pages[-1]) < char_limit:
                sub_line = sub_pages.pop(-1)
                page_size += len(sub_line)
                page.append(sub_line)

            # yield all the sub-lines at once.
            yield from map(wrapper.format, sub_pages) if wrapper else sub_pages

        # Otherwise it should be added to the next page.
        else:
            page_size += len(line)
            page.append(line)

    # This catches the likely dangling page after iteration ends.
    if page:
        yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page)


@typing.overload
def paginate_string(
    lines: collections.AsyncIterator[str],
    /,
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> collections.AsyncIterator[str]:
    ...


@typing.overload
def paginate_string(
    lines: collections.Iterator[str],
    /,
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> collections.Iterator[str]:
    ...


def paginate_string(
    lines: _internal.IterableT[str],
    /,
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> _internal.IteratorT[str]:
    """Lazily paginate an iterator of lines.

    Parameters
    ----------
    lines : collections.abc.Iterator[str] | collections.abc.AsyncIterator[str]
        The iterator of lines to paginate. This iterator may be asynchronous or synchronous.
    char_limit
        The limit for how many characters should be included per yielded page.
    line_limit
        The limit for how many lines should be included per yielded page.
    wrapper
        A wrapper for each yielded page. This should leave "{}" in it
        to be replaced by the page's content.

    Returns
    -------
    collections.abc.AsyncIterator[str] | collections.abc.Iterator[str]
        An iterator of each page's content.
    """
    if isinstance(lines, collections.AsyncIterable):
        return async_paginate_string(lines, char_limit=char_limit, line_limit=line_limit, wrapper=wrapper)

    return sync_paginate_string(lines, char_limit=char_limit, line_limit=line_limit, wrapper=wrapper)


async def aenumerate(iterable: collections.AsyncIterable[_T], /) -> collections.AsyncIterator[tuple[int, _T]]:
    """Async equivalent of [enumerate][].

    Parameters
    ----------
    iterable
        The async iterable to enumerate.

    Returns
    -------
    collections.abc.AsyncIterator[tuple[int, _T]]
        The enumerated async iterator.
    """
    counter = -1
    async for value in iterable:
        counter += 1
        yield (counter, value)


class Page:
    """Represents a pagianted response."""

    __slots__ = ("_attachments", "_content", "_embeds")

    @typing.overload
    def __init__(
        self,
        content: typing.Union[str, hikari.UndefinedType] = hikari.UNDEFINED,
        *,
        attachment: hikari.UndefinedOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedOr[collections.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[collections.Sequence[hikari.Embed]] = hikari.UNDEFINED,
    ) -> None:
        ...

    @typing.overload
    def __init__(
        self,
        content: hikari.Resourceish,
        *,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[collections.Sequence[hikari.Embed]] = hikari.UNDEFINED,
    ) -> None:
        ...

    @typing.overload
    def __init__(
        self,
        content: hikari.Embed,
        *,
        attachment: hikari.UndefinedOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedOr[collections.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
    ) -> None:
        ...

    def __init__(
        self,
        content: typing.Union[str, hikari.Embed, hikari.Resourceish, hikari.UndefinedType] = hikari.UNDEFINED,
        *,
        attachment: hikari.UndefinedOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedOr[collections.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        # TODO: come up with a system for passing other components per-response.
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[collections.Sequence[hikari.Embed]] = hikari.UNDEFINED,
    ) -> None:
        """Initialise a response page.

        Parameters
        ----------
        content
            The message content to send.

            If this is a [hikari.Embed][hikari.embeds.Embed] and no `embed` nor
            `embeds` kwarg is provided, then this will instead be treated as an
            embed. This allows for simpler syntax when sending an embed alone.

            Likewise, if this is a [hikari.Resource][hikari.files.Resource],
            then the content is instead treated as an attachment if no
            `attachment` and no `attachments` kwargs are provided.
        attachment
            A singular attachment to send.
        attachments
            Up to 10 attachments to include in the response.
        embed
            A singular embed to send.
        embeds
            Up to 10 embeds to include in the response.

        Raises
        ------
        ValueError
            Raised for any of the following reasons:

            * When both `attachment` and `attachments` are provided.
            * When both `embed` and `embeds` are passed.
        """
        if attachment is not hikari.UNDEFINED:
            if attachments is not hikari.UNDEFINED:
                raise ValueError("Cannot specify both attachment and attachments")

            attachments = [attachment]

        elif (
            attachments is hikari.UNDEFINED
            and content is not hikari.UNDEFINED
            and not isinstance(content, (str, hikari.Embed))
        ):
            attachments = [content]
            content = hikari.UNDEFINED

        if embed is not hikari.UNDEFINED:
            if embeds is not hikari.UNDEFINED:
                raise ValueError("Cannot specify both embed and embeds")

            embeds = [embed]

        elif embeds is hikari.UNDEFINED and isinstance(content, hikari.Embed):
            embeds = [content]
            content = hikari.UNDEFINED

        self._attachments = attachments
        self._content = typing.cast("hikari.UndefinedOr[str]", content)
        self._embeds = embeds

    @classmethod
    def from_entry(cls, entry: EntryT, /) -> Page:
        """Create a Page from a [EntryT][yuyo.pagination.EntryT].

        Parameters
        ----------
        entry
            The [EntryT][yuyo.pagination.EntryT] to make a page from.

        Returns
        -------
        Page
            The created page.
        """
        if isinstance(entry, tuple):
            content, embed = entry
            return cls(content=content, embed=embed)

        return entry

    def to_kwargs(self) -> _ResponseKwargs:
        """Form create message `**kwargs` for this page.

        Returns
        -------
        dict[str, Any]
            The create message kwargs for this page.
        """
        return {"attachments": self._attachments, "content": self._content, "embeds": self._embeds}


class Paginator:
    """Standard implementation of a paginator.

    To use this with components or reactions see the following classes:

    * [ComponentPaginator][yuyo.components.ComponentPaginator]
    * [ReactionPaginator][yuyo.reactions.ReactionPaginator]
    """

    __slots__ = ("_buffer", "_index", "_iterator")

    def __init__(self, iterator: _internal.IteratorT[EntryT], /) -> None:
        """Initialise a paginator.

        Parameters
        ----------
        iterator : collections.Iterator[yuyo.pagination.EntryT] | collections.AsyncIterator[yuyo.pagination.EntryT]
            The iterator to paginate.

            This should be an iterator of [Page][yuyo.pagination.Page]s.
        """
        if not isinstance(
            iterator, (collections.Iterator, collections.AsyncIterator)
        ):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"Invalid value passed for `iterator`, expected an iterator but got {type(iterator)}")

        self._buffer: list[Page] = []
        self._index: int = -1
        self._iterator: typing.Optional[_internal.IteratorT[EntryT]] = iterator

    @property
    def has_finished_iterating(self) -> bool:
        """Whether this has finished iterating over the original iterator."""
        return self._iterator is None

    def close(self) -> None:
        """Close the paginator."""
        self._buffer.clear()
        self._index = -1
        self._iterator = None

    @property
    def _is_behind_buffer(self) -> bool:
        return len(self._buffer) >= self._index + 2

    async def step_forward(self) -> typing.Optional[Page]:
        """Move this forward a page.

        Returns
        -------
        Page | None
            The next page in this paginator, or [None][] if this is already on
            the last page.
        """
        # Check to see if we're behind the buffer before trying to go forward in the generator.
        if self._is_behind_buffer:
            self._index += 1
            return self._buffer[self._index]

        # The iterator is finished and cannot be pushed any further.
        if not self._iterator:
            return None  # MyPy

        # If entry is not None then the generator's position was pushed forwards.
        if entry := await _internal.seek_iterator(self._iterator, default=None):
            page = Page.from_entry(entry)
            self._index += 1
            self._buffer.append(page)
            return page

        # Otherwise the generator has been depleted.
        self._iterator = None
        return None  # MyPy

    def step_back(self) -> typing.Optional[Page]:
        """Move back a page.

        Returns
        -------
        Page | None
            The previous page in this paginator.

            This will be [None][] if this is already on the first page or if
            the paginator hasn't been moved forward to the first entry yet.
        """
        if self._index > 0:
            self._index -= 1
            return self._buffer[self._index]

        return None  # MyPy compat

    def jump_to_first(self) -> typing.Optional[Page]:
        """Jump to the first page.

        Returns
        -------
        Page | None
            The first page in this paginator.

            This will be [None][] if this is already on the first page or if
            the paginator hasn't been moved forward to the first entry yet.
        """
        # -1 indicates this hasn't started yet and 0 indicates this is already
        # on the first entry.
        if self._index > 0:
            self._index = 0
            return self._buffer[0]

        return None  # MyPy compat

    async def jump_to_last(self) -> typing.Optional[Page]:
        """Jump to the last page.

        Returns
        -------
        Page | None
            The last page in this paginator, or [None][] if this is already on
            the last page.
        """
        if self._iterator:
            self._buffer.extend(map(Page.from_entry, await _internal.collect_iterable(self._iterator)))
            self._iterator = None

        if self._buffer and self._is_behind_buffer:
            self._index = len(self._buffer) - 1
            return self._buffer[-1]

        return None  # MyPy compat
