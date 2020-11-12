# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020, Faster Speeding
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
from __future__ import annotations

__slots__: typing.Sequence[str] = ["AbstractPaginator", "Paginator", "PaginatorPool"]

import abc
import asyncio
import datetime
import textwrap
import typing

from hikari import embeds
from hikari import emojis
from hikari import errors
from hikari import snowflakes
from hikari import traits
from hikari import undefined
from hikari.events import lifetime_events
from hikari.events import reaction_events

from yuyo import backoff

if typing.TYPE_CHECKING:
    from hikari import messages
    from hikari import users


LEFT_TRIANGLE: typing.Final[emojis.UnicodeEmoji] = emojis.UnicodeEmoji(
    "\N{BLACK LEFT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to go back an entry."""
STOP_SQUARE: typing.Final[emojis.UnicodeEmoji] = emojis.UnicodeEmoji(
    "\N{BLACK SQUARE FOR STOP}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to close a menu."""
RIGHT_TRIANGLE: typing.Final[emojis.UnicodeEmoji] = emojis.UnicodeEmoji(
    "\N{BLACK RIGHT-POINTING TRIANGLE}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to continue to the next entry."""
SKULL_AND_CROSSBONES: typing.Final[emojis.UnicodeEmoji] = emojis.UnicodeEmoji(
    "\N{SKULL AND CROSSBONES}\N{VARIATION SELECTOR-16}"
)
"""The emoji used for the lesser-enabled skip to last entry button."""
END = "END"
"""A return value used by `AbstractPaginator.on_reaction_modify`.

This indicates that the paginator should be removed from the pool.
"""
END_AND_REMOVE = "END_AND_REMOVE"
"""A return value used by `AbstractPaginator.on_reaction_modify`.

This indicates that the paginator should be removed from the pool,
removing any reactions on it's message in the process.
"""
EntryT = typing.Tuple[undefined.UndefinedOr[str], undefined.UndefinedOr[embeds.Embed]]
"""A type hint used to represent a paginator entry.

This should be a tuple of the string message content or `hikari.undefined.UNDEFINED`
to the message's embed if set else `hikari.undefined.UNDEFINED`.
"""
ValueT = typing.TypeVar("ValueT")
"""A type hint used to represent the type handled by an iterator."""
IteratorT = typing.Union[typing.AsyncIterator[ValueT], typing.Iterator[ValueT]]
"""A type hint used in places where both iterators and async-iterators are supported."""


class AbstractPaginator(abc.ABC):
    """The interface for a paginator handled within the `PaginatorPool`."""

    __slots__: typing.Sequence[str] = ()

    @property
    @abc.abstractmethod
    def authors(self) -> typing.AbstractSet[snowflakes.Snowflake]:
        """The authors/owner of a enabled paginator.

        !!! note
            If this is empty then the paginator is considered public and
            any user will be able to trigger it.

        Returns
        -------
        typing.AbstractSet[hikari.snowflakes.Snowflake]
            A set of the owner user IDs.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def expired(self) -> bool:
        """Whether this paginator has ended.

        Returns
        -------
        bool
            Whether this paginator has ended.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def last_triggered(self) -> datetime.datetime:
        """When this paginator was last triggered.

        !!! note
            If it hasn't ever been triggered then this will be when it was created.

        Returns
        -------
        datetime.datetime
            When this paginator was last triggered.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def locked(self) -> bool:
        """Whether this paginator has been locked by a call to it.

        Returns
        -------
        bool
            Whether this paginator has been locked by a call to it.
        """
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def triggers(self) -> typing.Sequence[emojis.Emoji]:
        """The enabled trigger emojis for this paginator.

        Returns
        -------
        typing.Sequence[emojis.Emoji]
            A sequence of the emojis that are enabled as triggers for
            this paginator.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def add_author(self, user: snowflakes.SnowflakeishOr[users.User], /) -> None:
        """Add a author/owner to this paginator.

        Parameters
        ----------
        user : hikari.snowflakes.SnowflakeishOr[hikari.users.User]
            The user to add as an owner for this paginator.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def remove_author(self, user: snowflakes.SnowflakeishOr[users.User], /) -> None:
        """Remove a author/owner from this paginator.

        !!! note
            If the provided user isn't already a registered owner of this paginator
            then this should pass silently without raising.

        Parameters
        ----------
        user : hikari.snowflakes.SnowflakeishOr[hikari.users.User]
            The user to remove from this paginator's owners..
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def deregister_message(self, *, remove_reactions: bool = False) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def register_message(self, message: messages.Message, /) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def on_reaction_event(self, emoji: emojis.Emoji, user_id: snowflakes.Snowflake) -> typing.Optional[str]:
        raise NotImplementedError


async def _delete_message(message: messages.Message, /) -> None:
    retry = backoff.Backoff()

    async for _ in retry:
        try:
            await message.delete()

        except (errors.NotFoundError, errors.ForbiddenError):  # TODO: better permission handling.
            return

        except errors.InternalServerError:
            continue

        except errors.RateLimitedError as exc:
            retry.set_next_backoff(exc.retry_after)

        else:
            break


async def collect_iterator(iterator: IteratorT[ValueT], /) -> typing.MutableSequence[ValueT]:
    if isinstance(iterator, typing.AsyncIterator):
        return [value async for value in iterator]

    if isinstance(iterator, typing.Iterator):
        return list(iterator)

    raise ValueError(f"{type(iterator)!r} is not a valid iterator")


async def seek_iterator(iterator: IteratorT[ValueT], /) -> typing.Optional[ValueT]:
    value: typing.Optional[ValueT] = None
    if isinstance(iterator, typing.AsyncIterator):
        async for value in iterator:
            break

    elif isinstance(iterator, typing.Iterator):
        for value in iterator:
            break

    else:
        raise ValueError(f"{type(iterator)!r} is not a valid iterator")

    return value


def _process_known_custom_emoji(emoji: emojis.Emoji, /) -> emojis.Emoji:
    # For the sake of equality checks we need to ensure we're handling CustomEmoji rather than KnownCustomEmoji
    if isinstance(emoji, emojis.KnownCustomEmoji):
        return emojis.CustomEmoji(id=emoji.id, name=emoji.name, is_animated=emoji.is_animated)

    return emoji


class Paginator(AbstractPaginator):
    __slots__: typing.Sequence[str] = (
        "_buffer",
        "_emoji_mapping",
        "_iterator",
        "_index",
        "_authors",
        "_last_triggered",
        "_locked",
        "message",
        "timeout",
        "_triggers",
    )

    def __init__(
        self,
        first_entry: EntryT,
        iterator: typing.Union[IteratorT[EntryT]],
        *,
        authors: typing.Optional[typing.Iterable[snowflakes.SnowflakeishOr[users.User]]],
        triggers: typing.Sequence[emojis.Emoji] = (
            LEFT_TRIANGLE,
            STOP_SQUARE,
            RIGHT_TRIANGLE,
        ),
        timeout: typing.Optional[datetime.timedelta] = None,
    ) -> None:
        if isinstance(iterator, typing.Iterator):
            raise ValueError(f"Invalid value passed for `iterator`, expected an iterator but got {type(iterator)}")

        self._authors = set(map(snowflakes.Snowflake, authors)) if authors else set()
        self._buffer: typing.MutableSequence[EntryT] = [first_entry]
        self._emoji_mapping: typing.Mapping[
            typing.Union[emojis.Emoji, snowflakes.Snowflake],
            typing.Callable[[], typing.Coroutine[typing.Any, typing.Any, typing.Union[EntryT, None, str]]],
        ] = {
            LEFT_TRIANGLE: self.on_previous,
            STOP_SQUARE: self.on_disable,
            RIGHT_TRIANGLE: self.on_next,
            SKULL_AND_CROSSBONES: self.on_last,
        }
        self._index = 0
        self._iterator = iterator
        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        self._locked = False
        self.message: typing.Optional[messages.Message] = None
        self.timeout = timeout or datetime.timedelta(seconds=30)
        self._triggers = tuple(_process_known_custom_emoji(emoji) for emoji in triggers)

    @property
    def authors(self) -> typing.AbstractSet[snowflakes.Snowflake]:
        return frozenset(self._authors)

    @property
    def expired(self) -> bool:
        return self.timeout < datetime.datetime.now(tz=datetime.timezone.utc) - self._last_triggered

    @property
    def last_triggered(self) -> datetime.datetime:
        return self._last_triggered

    @property
    def locked(self) -> bool:
        return self._locked

    @property
    def triggers(self) -> typing.Sequence[emojis.Emoji]:
        return self._triggers

    async def on_disable(self) -> str:
        if message := self.message:
            self.message = None
            # We create a task here rather than awaiting this to ensure the instance is marked as ended as soon as
            # possible.
            asyncio.create_task(_delete_message(message))

        return END

    async def on_first(self) -> typing.Optional[EntryT]:
        if self._index == 0:
            return None

        return self._buffer[0]

    async def on_next(self) -> typing.Optional[EntryT]:
        # Check to see if we're behind the buffer before trying to go forward in the generator.
        if len(self._buffer) < self._index + 1:
            self._index += 1
            return self._buffer[self._index]

        # If entry is not None then the generator's position was pushed forwards.
        if (entry := await seek_iterator(self._iterator)) is not None:
            self._index += 1
            self._buffer.append(entry)

        return entry

    async def on_last(self) -> typing.Optional[EntryT]:
        self._locked = True
        if isinstance(self._iterator, typing.AsyncIterator):
            self._buffer.extend([embed async for embed in self._iterator])

        elif isinstance(self._iterator, typing.Iterator):
            self._buffer.extend(self._iterator)

        self._locked = False

        if self._buffer:
            self._index = len(self._buffer) - 1
            return self._buffer[-1]

        return None

    async def on_previous(self) -> typing.Optional[EntryT]:
        if self._index <= 0:
            return None

        self._index -= 1
        return self._buffer[self._index]

    def add_author(self, user: snowflakes.SnowflakeishOr[users.User], /) -> None:
        self._authors.add(snowflakes.Snowflake(user))

    def remove_author(self, user: snowflakes.SnowflakeishOr[users.User], /) -> None:
        try:
            self._authors.remove(snowflakes.Snowflake(user))
        except KeyError:
            pass

    async def deregister_message(self, remove_reactions: bool = False) -> None:
        if message := self.message:
            self.message = None
            # TODO: check if we can just clear the reactions before doing this using the cache.
            for emoji in self._triggers:
                retry = backoff.Backoff()

                async for _ in retry:
                    try:
                        await message.remove_reaction(emoji)

                    except (errors.NotFoundError, errors.ForbiddenError):
                        return

                    except errors.RateLimitedError as exc:
                        retry.set_next_backoff(exc.retry_after)

                    except errors.InternalServerError:
                        continue

                    else:
                        break

    async def register_message(self, message: messages.Message, /) -> None:
        self.message = message
        for emoji in self._triggers:
            retry = backoff.Backoff()
            async for _ in retry:
                try:
                    await message.add_reaction(emoji)

                except (errors.NotFoundError, errors.ForbiddenError):
                    return

                except errors.RateLimitedError as exc:
                    retry.set_next_backoff(exc.retry_after)

                except errors.InternalServerError:
                    continue

                else:
                    break

    async def on_reaction_event(self, emoji: emojis.Emoji, user_id: snowflakes.Snowflake) -> typing.Optional[str]:
        if self.expired:
            return END_AND_REMOVE

        if self.message is None or self._authors and user_id not in self._authors or self._locked:
            return None

        method = self._emoji_mapping.get(emoji)
        if emoji not in self._triggers or not method:
            return None

        result = await method()
        if isinstance(result, str) or result is None:
            return result

        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        retry = backoff.Backoff()

        async for _ in retry:
            # Mypy makes the false assumption that this value will stay as None while this function yields.
            if self.message is None:
                break  # type: ignore[unreachable]

            try:
                await self.message.edit(content=result[0], embed=result[1])

            except errors.InternalServerError:
                continue

            except errors.RateLimitedError as exc:
                retry.set_next_backoff(exc.retry_after)

            except (errors.NotFoundError, errors.ForbiddenError):
                return END

        return None


class PaginatorPool:
    __slots__: typing.Sequence[str] = ("blacklist", "_gc_task", "_listeners", "_rest")

    def __init__(self, rest: traits.RESTAware, dispatch: typing.Optional[traits.DispatcherAware] = None, /) -> None:
        if dispatch is None and isinstance(rest, traits.DispatcherAware):
            dispatch = rest

        if dispatch is None:
            raise ValueError("Missing dispatcher aware client.")

        self.blacklist: typing.MutableSequence[snowflakes.Snowflake] = []
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._listeners: typing.MutableMapping[snowflakes.Snowflake, AbstractPaginator] = {}
        self._rest = rest
        dispatch.dispatcher.subscribe(lifetime_events.StartingEvent, self._on_starting_event)
        dispatch.dispatcher.subscribe(lifetime_events.StoppingEvent, self._on_stopping_event)
        dispatch.dispatcher.subscribe(reaction_events.ReactionAddEvent, self._on_reaction_event)
        dispatch.dispatcher.subscribe(reaction_events.ReactionDeleteEvent, self._on_reaction_event)

    async def _gc(self) -> None:
        while True:
            for listener_id, listener in tuple(self._listeners.items()):
                if not listener.expired or listener_id not in self._listeners:
                    continue

                del self._listeners[listener_id]
                # This may slow this gc task down but the more we yield the better.
                await listener.deregister_message(remove_reactions=True)

            await asyncio.sleep(5)  # TODO: is this a good time?

    async def _on_reaction_event(
        self, event: typing.Union[reaction_events.ReactionAddEvent, reaction_events.ReactionDeleteEvent], /
    ) -> None:
        if event.user_id in self.blacklist:
            return

        if listener := self._listeners.get(event.message_id):
            result = await listener.on_reaction_event(event.emoji, user_id=event.user_id)
            if result is END and event.message_id in self._listeners:
                del self._listeners[event.message_id]
                await listener.deregister_message(result is END_AND_REMOVE)

    async def _on_starting_event(self, _: lifetime_events.StartingEvent, /) -> None:
        await self.open()

    async def _on_stopping_event(self, _: lifetime_events.StoppingEvent, /) -> None:
        await self.close()

    def add_paginator(self, message: messages.Message, /, paginator: AbstractPaginator) -> None:
        self._listeners[message.id] = paginator

    def get_paginator(
        self, message: snowflakes.SnowflakeishOr[messages.Message], /
    ) -> typing.Optional[AbstractPaginator]:
        return self._listeners.get(snowflakes.Snowflake(message))

    def remove_paginator(
        self, message: snowflakes.SnowflakeishOr[messages.Message], /
    ) -> typing.Optional[AbstractPaginator]:
        return self._listeners.pop(snowflakes.Snowflake(message))

    async def close(self) -> None:
        if self._gc_task is not None:
            self._gc_task.cancel()
            listeners = self._listeners
            self._listeners = {}
            await asyncio.gather(*(listener.deregister_message() for listener in listeners.values()))

    async def open(self) -> None:
        if self._gc_task is None:
            self._gc_task = asyncio.create_task(self._gc())
            self.blacklist.append((await self._rest.rest.fetch_my_user()).id)


async def string_paginator(
    lines: IteratorT[str],
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> typing.AsyncIterator[typing.Tuple[str, int]]:
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
    typing.AsyncIterator[typing.Tuple[builtins.str, builtins.int]]
        An async iterator of page tuples (string context to int zero-based index).
    """
    if wrapper:
        char_limit -= len(wrapper) + 2

    page_number = -1
    page_size = 0
    page: typing.MutableSequence[str] = []

    while (line := await seek_iterator(lines)) is not None:
        # If the page is already populated and adding the current line would bring it over one of the predefined limits
        # then we want to yield this page.
        if len(page) >= line_limit or page and page_size + len(line) > char_limit:
            yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page), (page_number := page_number + 1)
            page.clear()
            page_size = 0

        # If the current line doesn't fit into a page then we can assume the current page was yielded and that we need
        # to split it up into sub-pages to yield.
        if len(line) >= char_limit:
            sub_pages = textwrap.wrap(
                line, width=char_limit, drop_whitespace=False, break_on_hyphens=False, expand_tabs=False
            )

            # If the last page could possible fit into a page with other lines then added it to the next page
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

    # This catches the likely dangling pages after iteration ends.
    if page:
        yield wrapper.format("\n".join(page)) if wrapper else "\n".join(page), page_number + 1
