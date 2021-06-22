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
"""Utilities used for handling reaction based paginated messages."""

from __future__ import annotations

__slots__: typing.Sequence[str] = [
    "AbstractPaginator",
    "Paginator",
    "PaginatorPool",
    "async_string_paginator",
    "sync_string_paginator",
    "string_paginator",
]

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
    from hikari import channels
    from hikari import messages
    from hikari import users
    from hikari.api import event_manager


LEFT_DOUBLE_TRIANGLE: typing.Final[emojis.UnicodeEmoji] = emojis.UnicodeEmoji(
    "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\N{VARIATION SELECTOR-16}"
)
"""The emoji used to go back to the first entry."""
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
RIGHT_DOUBLE_TRIANGLE: typing.Final[emojis.UnicodeEmoji] = emojis.UnicodeEmoji(
    "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\N{VARIATION SELECTOR-16}"
)
"""The emoji used for the lesser-enabled skip to last entry button."""
END = "END"
"""A return value used by `AbstractPaginator.on_reaction_event`.

This indicates that the paginator should be removed from the pool.
"""
DefaultT = typing.TypeVar("DefaultT")
"""A type hint used to represent a "default" argument provided to a function."""
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
    async def close(self, *, remove_reactions: bool = False) -> None:
        """Close this paginator and deregister any previously registered message.

        Other Parameters
        ----------------
        remove_reactions : builtins.bool
            Whether this should remove the reactions that were being used to
            paginate through this from the previously registered message.
            This defaults to `builtins.False`.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def open(
        self,
        *,
        message: typing.Optional[snowflakes.SnowflakeishOr[messages.Message]] = None,
        add_reactions: bool = True,
    ) -> typing.Optional[messages.Message]:
        """Start this paginator and link it to a message.

        Other Parameters
        ----------------
        message : typing.Optional[hikari.messages.Message]
            If already created, the message this paginator should target.
            If left as `builtins.None` then this call will create a message
            in the channel provided when initiating the paginator.
        add_reactions : bool
            Whether this should also add reactions that'll be used to paginate
            over this resource.
            This defaults to `builtins.True`.

        !!! note
            Calling this multiple times will replace the previously registered message.

        Returns
        -------
        typing.Optional[hikari.messages.Message]
            The message that this paginator created if `message_id` was left as `builtins.None`
            else `builtins.None`.

        Raises
        ------
        ValueError
            If the provided iterator didn't yield any content for the first message.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def on_reaction_event(self, emoji: emojis.Emoji, user_id: snowflakes.Snowflake) -> typing.Optional[str]:
        """The logic for handling reaction pagination.

        !!! note
            This should generally speaking only be called on ReactionAddEvent
            and ReactionDeleteEvent.

        Parameters
        ----------
        emoji : hikari.emojis.Emoji
            The unicode or custom emoji being added or removed in this event.
        user_id : hikari.snowflakes.Snowflake
            The ID of the user adding or removing this reaction.

        Returns
        -------
        typing.Optional[str]
            This will either be a string command ('"END"' to signal that the
            paginator has been de-registered and should be removed from the
            pool) or `builtins.None`.
        """
        raise NotImplementedError


async def _collect_iterator(iterator: IteratorT[ValueT], /) -> typing.MutableSequence[ValueT]:
    """Collect the rest of an async or sync iterator into a mutable sequence

    Parameters
    ----------
    iterator : typing.union[typing.AsyncIterator[ValueT], typing.Iterator[ValueT]]
        The iterator to collect. This iterator may be asynchronous or synchronous.

    Returns
    -------
    ValueT
        A sequence of the remaining values in the iterator.
    """
    if isinstance(iterator, typing.AsyncIterator):
        return [value async for value in iterator]

    if isinstance(iterator, typing.Iterator):
        return list(iterator)

    raise ValueError(f"{type(iterator)!r} is not a valid iterator")


async def _seek_iterator(iterator: IteratorT[ValueT], /, default: DefaultT) -> typing.Union[ValueT, DefaultT]:
    """Get the next value in an async or sync iterator."""
    if isinstance(iterator, typing.AsyncIterator):
        return await _seek_async_iterator(iterator, default=default)

    if isinstance(iterator, typing.Iterator):
        return _seek_sync_iterator(iterator, default=default)

    raise ValueError(f"{type(iterator)!r} is not a valid iterator")


async def _seek_async_iterator(
    iterator: typing.AsyncIterator[ValueT], /, default: DefaultT
) -> typing.Union[ValueT, DefaultT]:
    """Get the next value in an async iterator."""
    async for value in iterator:
        return value

    return default


def _seek_sync_iterator(iterator: typing.Iterator[ValueT], /, default: DefaultT) -> typing.Union[ValueT, DefaultT]:
    """Get the next value in an async iterator."""
    return next(iterator, default=default)


def _process_known_custom_emoji(emoji: emojis.Emoji, /) -> emojis.Emoji:
    # For the sake of equality checks we need to ensure we're handling CustomEmoji rather than KnownCustomEmoji
    if isinstance(emoji, emojis.KnownCustomEmoji):
        return emojis.CustomEmoji(id=emoji.id, name=emoji.name, is_animated=emoji.is_animated)

    return emoji


class Paginator(AbstractPaginator):
    """The standard implementation of `AbstractPaginator`.

    Parameters
    ----------
    rest : hikari.traits.RESTAware
        The REST aware client this should be bound to.
    channel : hikari.snowflakes.SnowflakeishOr[hikari.channels.TextChannel]
        The ID of the text channel this iterator targets.
    iterator : Iterator[typing.Tuple[undefined.UndefinedOr[str], undefined.UndefinedOr[embeds.Embed]]]
        Either an asynchronous or synchronous iterator of the entries this
        should paginate through.
        Entry[0] represents the message's possible content and can either be
        `builtins.str` or `hikari.undefined.UNDEFINED` and Entry[1] represents
        the message's possible embed and can either be `hikari.embeds.Embed`
        or `hikari.undefined.UNDEFINED`.
    authors : typing.Iterable[hikari.snowflakes.SnowflakeishOr[hikari.users.User]]
        An iterable of IDs of the users who can call this paginator.
        If left empty then all users will be able to call this
        paginator.

    Other Parameters
    ----------------
    timeout : datetime.timedelta
        How long it should take for this paginator to timeout.
        This defaults to a timdelta of 30 seconds.
    """

    __slots__: typing.Sequence[str] = (
        "_authors",
        "_buffer",
        "_channel_id",
        "_emoji_mapping",
        "_index",
        "_iterator",
        "_last_triggered",
        "_locked",
        "_message_id",
        "_rest",
        "timeout",
        "_triggers",
    )

    def __init__(
        self,
        rest: traits.RESTAware,
        channel: snowflakes.SnowflakeishOr[channels.TextChannel],
        iterator: typing.Union[IteratorT[EntryT]],
        *,
        authors: typing.Iterable[snowflakes.SnowflakeishOr[users.User]],
        triggers: typing.Sequence[emojis.Emoji] = (
            LEFT_TRIANGLE,
            STOP_SQUARE,
            RIGHT_TRIANGLE,
        ),
        timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    ) -> None:
        if not isinstance(iterator, (typing.Iterator, typing.AsyncIterator)):
            raise ValueError(f"Invalid value passed for `iterator`, expected an iterator but got {type(iterator)}")

        self._authors = set(map(snowflakes.Snowflake, authors))
        self._buffer: typing.MutableSequence[EntryT] = []
        self._channel_id = channel
        self._emoji_mapping: typing.Mapping[
            typing.Union[emojis.Emoji, snowflakes.Snowflake],
            typing.Callable[[], typing.Coroutine[typing.Any, typing.Any, typing.Union[EntryT, None, str]]],
        ] = {
            LEFT_DOUBLE_TRIANGLE: self._on_first,
            LEFT_TRIANGLE: self._on_previous,
            STOP_SQUARE: self._on_disable,
            RIGHT_TRIANGLE: self._on_next,
            RIGHT_DOUBLE_TRIANGLE: self._on_last,
        }
        self._index = 0
        self._iterator = iterator
        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        self._locked = False
        self._message_id: typing.Optional[snowflakes.Snowflake] = None
        self._rest = rest
        self.timeout = timeout
        self._triggers = tuple(_process_known_custom_emoji(emoji) for emoji in triggers)

    @property
    def authors(self) -> typing.AbstractSet[snowflakes.Snowflake]:
        # <<inherited docstring from AbstractPaginator>>.
        return frozenset(self._authors)

    @property
    def expired(self) -> bool:
        # <<inherited docstring from AbstractPaginator>>.
        return self.timeout < datetime.datetime.now(tz=datetime.timezone.utc) - self._last_triggered

    @property
    def last_triggered(self) -> datetime.datetime:
        # <<inherited docstring from AbstractPaginator>>.
        return self._last_triggered

    @property
    def locked(self) -> bool:
        # <<inherited docstring from AbstractPaginator>>.
        return self._locked

    @property
    def triggers(self) -> typing.Sequence[emojis.Emoji]:
        # <<inherited docstring from AbstractPaginator>>.
        return self._triggers

    async def _delete_message(self, message_id: snowflakes.Snowflake, /) -> None:
        retry = backoff.Backoff()

        async for _ in retry:
            try:
                await self._rest.rest.delete_message(self._channel_id, message_id)

            except (errors.NotFoundError, errors.ForbiddenError):  # TODO: attempt to check permissions first
                return

            except errors.InternalServerError:
                continue

            except errors.RateLimitedError as exc:
                retry.set_next_backoff(exc.retry_after)

            else:
                break

    async def _on_disable(self) -> str:
        if message_id := self._message_id:
            self._message_id = None
            # We create a task here rather than awaiting this to ensure the instance is marked as ended as soon as
            # possible.
            asyncio.create_task(self._delete_message(message_id))

        return END

    async def _on_first(self) -> typing.Optional[EntryT]:
        if self._index == 0:
            return None

        return self._buffer[0]

    async def _on_last(self) -> typing.Optional[EntryT]:
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

    async def _on_next(self) -> typing.Optional[EntryT]:
        # Check to see if we're behind the buffer before trying to go forward in the generator.
        if len(self._buffer) >= self._index + 2:
            self._index += 1
            return self._buffer[self._index]

        # If entry is not None then the generator's position was pushed forwards.
        if (entry := await _seek_iterator(self._iterator, default=None)) is not None:
            self._index += 1
            self._buffer.append(entry)

        return entry

    async def _on_previous(self) -> typing.Optional[EntryT]:
        if self._index <= 0:
            return None

        self._index -= 1
        return self._buffer[self._index]

    def add_author(self, user: snowflakes.SnowflakeishOr[users.User], /) -> None:
        # <<inherited docstring from AbstractPaginator>>.
        self._authors.add(snowflakes.Snowflake(user))

    def remove_author(self, user: snowflakes.SnowflakeishOr[users.User], /) -> None:
        # <<inherited docstring from AbstractPaginator>>.
        try:
            self._authors.remove(snowflakes.Snowflake(user))
        except KeyError:
            pass

    async def close(self, remove_reactions: bool = False) -> None:
        # <<inherited docstring from AbstractPaginator>>.
        if message_id := self._message_id:
            self._message_id = None
            retry = backoff.Backoff()
            # TODO: check if we can just clear the reactions before doing this using the cache.
            for emoji in self._triggers:
                retry.reset()
                async for _ in retry:
                    try:
                        await self._rest.rest.delete_my_reaction(self._channel_id, message_id, emoji)

                    except (errors.NotFoundError, errors.ForbiddenError):
                        return

                    except errors.RateLimitedError as exc:
                        retry.set_next_backoff(exc.retry_after)

                    except errors.InternalServerError:
                        continue

                    else:
                        break

    async def open(
        self,
        *,
        message: typing.Optional[snowflakes.SnowflakeishOr[messages.Message]] = None,
        add_reactions: bool = True,
        max_retries: int = 5,
        max_backoff: float = 2.0,
    ) -> typing.Optional[messages.Message]:
        # <<inherited docstring from AbstractPaginator>>.
        created_message: typing.Optional[messages.Message] = None
        if self._message_id is not None:
            return None

        retry = backoff.Backoff(max_retries=max_retries - 1, maximum=max_backoff)
        if message is None:
            entry = await self._on_next()

            if entry is None:
                raise ValueError("Paginator iterator yielded no pages.")

            async for _ in retry:
                try:
                    created_message = await self._rest.rest.create_message(
                        self._channel_id, content=entry[0], embed=entry[1]
                    )
                    message = created_message.id

                except errors.RateLimitedError as exc:
                    if exc.retry_after > max_backoff:
                        raise

                    retry.set_next_backoff(exc.retry_after)

                except errors.InternalServerError:
                    continue

                else:
                    break

            else:
                message = await self._rest.rest.create_message(self._channel_id, content=entry[0], embed=entry[1])

        message = snowflakes.Snowflake(message)
        self._message_id = message
        for emoji in self._triggers:
            retry.reset()
            async for _ in retry:
                try:
                    await self._rest.rest.add_reaction(self._channel_id, message, emoji)

                except errors.NotFoundError:
                    self._message_id = None
                    raise

                except errors.ForbiddenError:  # TODO: attempt to check permissions first
                    # If this is reached then we just don't have reaction permissions in the channel.
                    return created_message

                except errors.RateLimitedError as exc:
                    if exc.retry_after > max_backoff:
                        raise

                    retry.set_next_backoff(exc.retry_after)

                except errors.InternalServerError:
                    continue

                else:
                    break

            else:
                await self._rest.rest.add_reaction(self._channel_id, message, emoji)

        return created_message

    async def on_reaction_event(self, emoji: emojis.Emoji, user_id: snowflakes.Snowflake) -> typing.Optional[str]:
        # <<inherited docstring from AbstractPaginator>>.
        if self.expired:
            asyncio.create_task(self.close(remove_reactions=True))
            return END

        if self._message_id is None or self._authors and user_id not in self._authors or self._locked:
            return None

        method = self._emoji_mapping.get(emoji)
        if emoji not in self._triggers or not method:
            return None

        result = await method()
        if isinstance(result, str) or result is None:
            return END

        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        retry = backoff.Backoff()

        async for _ in retry:
            # Mypy makes the false assumption that this value will stay as None while this function yields.
            if self._message_id is None:
                break  # type: ignore[unreachable]

            try:
                await self._rest.rest.edit_message(
                    self._channel_id, self._message_id, content=result[0], embed=result[1]
                )

            except errors.InternalServerError:
                continue

            except errors.RateLimitedError as exc:
                retry.set_next_backoff(exc.retry_after)

            except (errors.NotFoundError, errors.ForbiddenError):
                return END

            else:
                break

        return None


class PaginatorPool:
    """A class which handles the events for multiple registered paginators.

    Parameters
    ----------
    rest : hikari.traits.RESTAware
        The REST aware client to register this paginator pool with.
    dispatch : typing.Optional[hikari.traits.DispatcherAware]
        The dispatcher aware client to register this paginator pool with.

        !!! note
            This may only be left as `builtins.None` if `rest` is dispatcher
            aware.

    Raises
    ------
    ValueError
        If `dispatch` is left as `builtins.None` when `rest` is not also
        dispatcher aware.
    """

    __slots__: typing.Sequence[str] = ("blacklist", "_events", "_gc_task", "_listeners", "_rest")

    def __init__(self, rest: traits.RESTAware, events: typing.Optional[traits.EventManagerAware] = None, /) -> None:
        if events is None and isinstance(rest, traits.EventManagerAware):
            events = rest

        if events is None:
            raise ValueError("Missing event manager aware client.")

        self.blacklist: typing.MutableSequence[snowflakes.Snowflake] = []
        self._events = events
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._listeners: typing.MutableMapping[snowflakes.Snowflake, AbstractPaginator] = {}
        self._rest = rest

    async def _gc(self) -> None:
        while True:
            for listener_id, listener in tuple(self._listeners.items()):
                if not listener.expired or listener_id not in self._listeners:
                    continue

                del self._listeners[listener_id]
                # This may slow this gc task down but the more we yield the better.
                await listener.close(remove_reactions=True)

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

    async def _on_starting_event(self, _: lifetime_events.StartingEvent, /) -> None:
        await self.open()

    async def _on_stopping_event(self, _: lifetime_events.StoppingEvent, /) -> None:
        await self.close()

    def add_paginator(
        self, message: snowflakes.SnowflakeishOr[messages.Message], /, paginator: AbstractPaginator
    ) -> None:
        """Add a paginator to this pool.

        !!! note
            This does not call `AbstractPaginator.open`.

        Parameters
        ----------
        message : hikari.snowflakes.SnowflakeishOr[hikari.messages.Message]
            The message ID to add register a paginator with.
        paginator : AbstractPaginator
            The object of the opened paginator to register in this pool.
        """
        self._listeners[snowflakes.Snowflake(message)] = paginator

    def get_paginator(
        self, message: snowflakes.SnowflakeishOr[messages.Message], /
    ) -> typing.Optional[AbstractPaginator]:
        """Get a reference to a paginator registered in this pool.

        !!! note
            This does not call `AbstractPaginator.close`.

        Parameters
        ----------
        message : hikari.snowflakes.SnowflakeishOr[hikari.messages.Message]
            The message ID to remove a paginator for.

        Returns
        -------
        AbstractPaginator
            The object of the registered paginator if found else `builtins.None`.
        """
        return self._listeners.get(snowflakes.Snowflake(message))

    def remove_paginator(
        self, message: snowflakes.SnowflakeishOr[messages.Message], /
    ) -> typing.Optional[AbstractPaginator]:
        """Remove a paginator from this pool.

        !!! note
            This does not call `AbstractPaginator.close`.

        Parameters
        ----------
        message : hikari.snowflakes.SnowflakeishOr[hikari.messages.Message]
            The message ID to remove a paginator for.

        Returns
        -------
        AbstractPaginator
            The object of the registered paginator if found else `builtins.None`.
        """
        return self._listeners.pop(snowflakes.Snowflake(message))

    def _try_unsubscribe(self, event_type: typing.Type[event_manager.EventT_co], callback: event_manager.CallbackT) -> None:
        try:
            self._events.event_manager.unsubscribe(event_type, callback)
        except (ValueError, LookupError):
            # TODO: add logging here
            pass

    async def close(self) -> None:
        """Close this pool by unregistering any tasks and event listeners registered by `PaginatorPool.open`."""
        if self._gc_task is not None:
            self._try_unsubscribe(lifetime_events.StartingEvent, self._on_starting_event)
            self._try_unsubscribe(lifetime_events.StoppingEvent, self._on_stopping_event)
            self._try_unsubscribe(reaction_events.ReactionAddEvent, self._on_reaction_event)
            self._try_unsubscribe(reaction_events.ReactionDeleteEvent, self._on_reaction_event)
            self._gc_task.cancel()
            listeners = self._listeners
            self._listeners = {}
            await asyncio.gather(*(listener.close() for listener in listeners.values()))

    async def open(self) -> None:
        """Start this pool by registering the required tasks and event listeners for it to function."""
        if self._gc_task is None:
            self._gc_task = asyncio.create_task(self._gc())
            self.blacklist.append((await self._rest.rest.fetch_my_user()).id)
            self._events.event_manager.subscribe(lifetime_events.StartingEvent, self._on_starting_event)
            self._events.event_manager.subscribe(lifetime_events.StoppingEvent, self._on_stopping_event)
            self._events.event_manager.subscribe(reaction_events.ReactionAddEvent, self._on_reaction_event)
            self._events.event_manager.subscribe(reaction_events.ReactionDeleteEvent, self._on_reaction_event)


@typing.overload
def string_paginator(
    lines: typing.Iterator[str],
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> typing.Iterator[typing.Tuple[str, int]]:
    ...


@typing.overload
def string_paginator(
    lines: typing.AsyncIterator[str],
    *,
    char_limit: int = 2000,
    line_limit: int = 25,
    wrapper: typing.Optional[str] = None,
) -> typing.AsyncIterator[typing.Tuple[str, int]]:
    ...


def string_paginator(
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
    """
    if isinstance(lines, typing.AsyncIterator):
        return async_string_paginator(lines, char_limit=char_limit, line_limit=line_limit, wrapper=wrapper)

    return sync_string_paginator(lines, char_limit=char_limit, line_limit=line_limit, wrapper=wrapper)


async def async_string_paginator(
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
    page: typing.MutableSequence[str] = []

    while (line := await _seek_async_iterator(lines, default=None)) is not None:
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


def sync_string_paginator(
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
    page: typing.MutableSequence[str] = []

    while (line := _seek_sync_iterator(lines, default=None)) is not None:
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
