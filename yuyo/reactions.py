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
"""Client for higher level callback based reaction menu handling."""

from __future__ import annotations

__all__: typing.Sequence[str] = [
    "AbstractReactionHandler",
    "ReactionClient",
    "ReactionHandler",
    "ReactionPaginator",
    "as_reaction_callback",
]

import abc
import asyncio
import datetime
import inspect
import typing

import alluka as alluka_
import hikari

from . import _internal
from . import backoff
from . import pagination

if typing.TYPE_CHECKING:
    from hikari import traits
    from hikari.api import event_manager as event_manager_api
    from typing_extensions import Self

    _EventT = typing.TypeVar("_EventT", bound=hikari.Event)


EventT = typing.Union[hikari.ReactionAddEvent, hikari.ReactionDeleteEvent]
CallbackSig = typing.Callable[..., typing.Coroutine[typing.Any, typing.Any, None]]
CallbackSigT = typing.TypeVar("CallbackSigT", bound=CallbackSig)


class HandlerClosed(Exception):
    """Error raised when a reaction handler has been closed."""


class AbstractReactionHandler(abc.ABC):
    """The interface for a reaction handler used with [yuyo.reactions.ReactionClient][]."""

    __slots__ = ()

    @property
    @abc.abstractmethod
    def has_expired(self) -> bool:
        """Whether this handler has ended."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def last_triggered(self) -> datetime.datetime:
        """When this handler was last triggered.

        !!! note
            If it hasn't ever been triggered then this will be when it was created.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def close(self) -> None:
        """Close this handler."""
        raise NotImplementedError

    @abc.abstractmethod
    async def open(self, message: hikari.Message, /) -> None:
        """Open this handler.

        Parameters
        ----------
        message
            The message to bind this handler to.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def on_reaction_event(self, event: EventT, /, *, alluka: typing.Optional[alluka_.abc.Client] = None) -> None:
        """Handle a reaction event.

        Parameters
        ----------
        event
            The event to handle.
        alluka
            The Alluka client to use for callback dependency injection during callback calls.

        Raises
        ------
        HandlerClosed
            If this reaction handler has been closed.
        """
        raise NotImplementedError


def as_reaction_callback(  # noqa: D103
    emoji_identifier: typing.Union[hikari.SnowflakeishOr[hikari.CustomEmoji], str], /
) -> typing.Callable[[CallbackSigT], CallbackSigT]:
    def decorator(callback: CallbackSigT, /) -> CallbackSigT:
        nonlocal emoji_identifier
        if isinstance(emoji_identifier, hikari.CustomEmoji):
            emoji_identifier = emoji_identifier.id

        callback.__emoji_identifier__ = emoji_identifier  # type: ignore
        return callback

    return decorator


class ReactionHandler(AbstractReactionHandler):
    """Standard basic implementation of a reaction handler."""

    __slots__ = ("_authors", "_callbacks", "_last_triggered", "_lock", "_message", "_timeout")

    def __init__(
        self,
        *,
        authors: typing.Iterable[hikari.SnowflakeishOr[hikari.User]] = (),
        timeout: datetime.timedelta = datetime.timedelta(seconds=30),
        load_from_attributes: bool = True,
    ) -> None:
        """Initialise a reaction handler.

        Parameters
        ----------
        authors
            An iterable of IDs of the users who can call this paginator.
            If left empty then all users will be able to call this
            paginator.
        timeout
            How long it should take for this paginator to timeout.
        """
        self._authors = set(map(hikari.Snowflake, authors))
        self._callbacks: typing.Dict[typing.Union[str, int], CallbackSig] = {}
        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        self._lock = asyncio.Lock()
        self._message: typing.Optional[hikari.Message] = None
        self._timeout = timeout

        if load_from_attributes and type(self) is not ReactionHandler:
            for _, value in inspect.getmembers(self):
                try:
                    identifier = value.__emoji_identifier__

                except AttributeError:
                    pass

                else:
                    self._callbacks[identifier] = value

    @property
    def authors(self) -> typing.AbstractSet[hikari.Snowflake]:
        """Set of the authors/owner of a enabled handler.

        !!! note
            If this is empty then the handler is considered public and
            any user will be able to trigger it.
        """
        return frozenset(self._authors)

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractReactionHandler>>.
        return self._timeout < datetime.datetime.now(tz=datetime.timezone.utc) - self._last_triggered

    @property
    def last_triggered(self) -> datetime.datetime:
        # <<inherited docstring from AbstractReactionHandler>>.
        return self._last_triggered

    @property
    def timeout(self) -> datetime.timedelta:
        """How long this handler will wait since the last event before timing out."""
        return self._timeout

    async def open(self, message: hikari.Message, /) -> None:
        self._message = message

    async def close(self) -> None:
        # <<inherited docstring from AbstractReactionHandler>>.
        self._message = None

    def add_callback(
        self,
        emoji_identifier: typing.Union[str, hikari.SnowflakeishOr[hikari.CustomEmoji]],
        callback: CallbackSig,
        /,
    ) -> Self:
        """Add a callback to this reaction handler.

        Parameters
        ----------
        emoji_identifier
            Identifier of the emoji this callback is for.

            This should be a snowfake if this is for a custom emoji or a string
            if this is for a unicode emoji.
        callback
            The callback to add.

            This should be a function that accepts a single parameter,
            which is the event that triggered this reaction.
        """
        if isinstance(emoji_identifier, hikari.CustomEmoji):
            emoji_identifier = emoji_identifier.id

        self._callbacks[emoji_identifier] = callback
        return self

    def remove_callback(
        self, emoji_identifier: typing.Union[str, hikari.SnowflakeishOr[hikari.CustomEmoji]], /
    ) -> None:
        """Remove a callback from this reaction handler.

        Parameters
        ----------
        emoji_identifier
            Identifier of the emoji the callback to remove is for.

            This should be a snowfake if this is for a custom emoji or a string
            if this is for a unicode emoji.
        """
        if isinstance(emoji_identifier, hikari.CustomEmoji):
            emoji_identifier = emoji_identifier.id

        del self._callbacks[emoji_identifier]

    def with_callback(
        self, emoji_identifier: typing.Union[str, hikari.SnowflakeishOr[hikari.CustomEmoji]], /
    ) -> typing.Callable[[CallbackSigT], CallbackSigT]:
        """Add a callback to this reaction handler through a decorator call.

        Parameters
        ----------
        emoji_identifier
            Identifier of the emoji this callback is for.

            This should be a snowfake if this is for a custom emoji or a string
            if this is for a unicode emoji.

        Returns
        -------
        typing.Callabke[[CallbackSigT], CallbackSigT]
            A decorator to add a callback to this reaction handler.
        """

        def decorator(callback: CallbackSigT, /) -> CallbackSigT:
            nonlocal emoji_identifier
            if isinstance(emoji_identifier, hikari.CustomEmoji):
                emoji_identifier = emoji_identifier.id

            self.add_callback(emoji_identifier, callback)
            return callback

        return decorator

    async def on_reaction_event(self, event: EventT, /, *, alluka: typing.Optional[alluka_.abc.Client] = None) -> None:
        # <<inherited docstring from AbstractReactionHandler>>.
        if self.has_expired:
            asyncio.create_task(self.close())
            raise

        if self._message is None or self._authors and event.user_id not in self._authors:
            return

        emoji_identifier = event.emoji_id or event.emoji_name
        assert emoji_identifier is not None

        method = self._callbacks.get(emoji_identifier)
        if not method:
            return

        if not self._lock:
            self._lock = asyncio.Lock()

        async with self._lock:
            if alluka:
                await alluka.call_with_async_di(method, event)

            else:
                await method(event)

            self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)


async def _delete_message(message: hikari.Message, /) -> None:
    retry = backoff.Backoff()

    async for _ in retry:
        try:
            await message.delete()

        except (hikari.NotFoundError, hikari.ForbiddenError):  # TODO: attempt to check permissions first
            return

        except hikari.InternalServerError:
            continue

        except hikari.RateLimitedError as exc:
            retry.set_next_backoff(exc.retry_after)

        else:
            break


class ReactionPaginator(ReactionHandler):
    """Standard implementation of a reaction handler for pagination."""

    __slots__ = ("_buffer", "_index", "_iterator", "_triggers")

    def __init__(
        self,
        iterator: _internal.IteratorT[pagination.EntryT],
        *,
        authors: typing.Iterable[hikari.SnowflakeishOr[hikari.User]],
        triggers: typing.Collection[str] = (
            pagination.LEFT_TRIANGLE,
            pagination.STOP_SQUARE,
            pagination.RIGHT_TRIANGLE,
        ),
        timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    ) -> None:
        """Initialise a reaction paginator.

        Parameters
        ----------
        iterator : typing.Iterator[yuyo.pagination.EntryT] | typing.AsyncIterator[yuyo.pagination.EntryT]
            Either an asynchronous or synchronous iterator of the entries this
            should paginate through.
            `entry[0]` represents the message's possible content and can either be
            [str][] or [hikari.undefined.UNDEFINED][] and `entry[1]` represents
            the message's possible embed and can either be [hikari.embeds.Embed][]
            or [hikari.undefined.UNDEFINED][].
        authors
            An iterable of IDs of the users who can call this paginator.
            If left empty then all users will be able to call this
            paginator.
        timeout
            How long it should take for this paginator to timeout.
        """
        if not isinstance(
            iterator, (typing.Iterator, typing.AsyncIterator)
        ):  # pyright: ignore reportUnnecessaryIsInstance
            raise ValueError(f"Invalid value passed for `iterator`, expected an iterator but got {type(iterator)}")

        super().__init__(authors=authors, timeout=timeout, load_from_attributes=False)
        self._buffer: typing.List[pagination.EntryT] = []
        self._index = -1
        self._iterator: typing.Optional[_internal.IteratorT[pagination.EntryT]] = iterator
        self._triggers = triggers

        if pagination.LEFT_DOUBLE_TRIANGLE in triggers:
            self.add_callback(pagination.LEFT_DOUBLE_TRIANGLE, self._on_first)

        if pagination.LEFT_TRIANGLE in triggers:
            self.add_callback(pagination.LEFT_TRIANGLE, self._on_previous)

        if pagination.STOP_SQUARE in triggers:
            self.add_callback(pagination.STOP_SQUARE, self._on_disable)

        if pagination.RIGHT_TRIANGLE in triggers:
            self.add_callback(pagination.RIGHT_TRIANGLE, self._on_next)

        if pagination.RIGHT_DOUBLE_TRIANGLE in triggers:
            self.add_callback(pagination.RIGHT_DOUBLE_TRIANGLE, self._on_last)

    async def _edit_message(
        self, *, content: hikari.UndefinedNoneOr[str], embed: hikari.UndefinedNoneOr[hikari.Embed]
    ) -> None:
        retry = backoff.Backoff()

        async for _ in retry:
            # Mypy makes the false assumption that this value will stay as None while this function yields.
            if self._message is None:
                break  # type: ignore[unreachable]

            try:
                await self._message.edit(content=content, embed=embed)

            except hikari.InternalServerError:
                continue

            except hikari.RateLimitedError as exc:
                retry.set_next_backoff(exc.retry_after)

            except (hikari.NotFoundError, hikari.ForbiddenError) as exc:
                raise HandlerClosed() from exc

            else:
                break

    async def _on_disable(self, _: EventT, /) -> None:
        if message := self._message:
            self._message = None
            # We create a task here rather than awaiting this to ensure the instance is marked as ended as soon as
            # possible.
            asyncio.create_task(_delete_message(message))

        raise HandlerClosed

    async def _on_first(self, _: EventT, /) -> None:
        if self._index != 0 and (first_entry := self._buffer[0] if self._buffer else await self.get_next_entry()):
            content, embed = first_entry
            await self._edit_message(content=content, embed=embed)

    async def _on_last(self, _: EventT, /) -> None:
        if self._iterator:
            self._buffer.extend(await _internal.collect_iterable(self._iterator))

        if self._buffer:
            self._index = len(self._buffer) - 1
            content, embed = self._buffer[-1]
            await self._edit_message(content=content, embed=embed)

    async def get_next_entry(self, /) -> typing.Optional[pagination.EntryT]:
        # Check to see if we're behind the buffer before trying to go forward in the generator.
        if len(self._buffer) >= self._index + 2:
            self._index += 1
            return self._buffer[self._index]

        # If entry is not None then the generator's position was pushed forwards.
        if self._iterator and (entry := await _internal.seek_iterator(self._iterator, default=None)):
            self._index += 1
            self._buffer.append(entry)
            return entry

    async def _on_next(self, _: EventT, /) -> None:
        if entry := await self.get_next_entry():
            content, embed = entry
            await self._edit_message(content=content, embed=embed)

    async def _on_previous(self, _: EventT, /) -> None:
        if self._index > 0:
            self._index -= 1
            content, embed = self._buffer[self._index]
            await self._edit_message(content=content, embed=embed)

    def add_author(self, user: hikari.SnowflakeishOr[hikari.User], /) -> Self:
        """Add a author/owner to this handler.

        Parameters
        ----------
        user
            The user to add as an owner for this handler.
        """
        self._authors.add(hikari.Snowflake(user))
        return self

    def remove_author(self, user: hikari.SnowflakeishOr[hikari.User], /) -> None:
        """Remove a author/owner from this handler.

        !!! note
            If the provided user isn't already a registered owner of this paginator
            then this should pass silently without raising.

        Parameters
        ----------
        user
            The user to remove from this handler's owners.
        """
        try:
            self._authors.remove(hikari.Snowflake(user))
        except KeyError:
            pass

    async def close(
        self,
        *,
        remove_reactions: bool = False,
        max_retries: int = 5,
        max_backoff: float = 2.0,
    ) -> None:
        """Close this handler and deregister any previously registered message.

        Parameters
        ----------
        remove_reactions
            Whether this should remove the reactions that were being used to
            paginate through this from the previously registered message.
        """
        if message := self._message:
            self._message = None
            if not remove_reactions:
                return

            retry = backoff.Backoff(max_retries=max_retries, maximum=max_backoff)
            # TODO: check if we can just clear the reactions before doing this using the cache.
            for emoji_name in self._triggers:
                retry.reset()
                async for _ in retry:
                    try:
                        await message.remove_reaction(emoji_name)

                    except (hikari.NotFoundError, hikari.ForbiddenError):
                        return

                    except hikari.RateLimitedError as exc:
                        retry.set_next_backoff(exc.retry_after)

                    except hikari.InternalServerError:
                        continue

                    else:
                        break

    async def open(
        self,
        message: hikari.Message,
        /,
        *,
        add_reactions: bool = True,
        max_retries: int = 5,
        max_backoff: float = 2.0,
    ) -> None:
        await super().open(message)
        if not add_reactions:
            return

        retry = backoff.Backoff(max_retries=max_retries - 1, maximum=max_backoff)
        for emoji_name in self._triggers:
            retry.reset()
            async for _ in retry:
                try:
                    await message.add_reaction(emoji_name)

                except hikari.NotFoundError:
                    self._message = None
                    raise

                except hikari.ForbiddenError:  # TODO: attempt to check permissions first
                    # If this is reached then we just don't have reaction permissions in the channel.
                    return

                except hikari.RateLimitedError as exc:
                    if exc.retry_after > max_backoff:
                        raise

                    retry.set_next_backoff(exc.retry_after)

                except hikari.InternalServerError:
                    continue

                else:
                    break

            else:
                await message.add_reaction(emoji_name)

    async def create_message(
        self,
        rest: hikari.api.RESTClient,
        channel_id: hikari.SnowflakeishOr[hikari.TextableChannel],
        /,
        *,
        add_reactions: bool = True,
        max_retries: int = 5,
        max_backoff: float = 2.0,
    ) -> hikari.Message:
        """Start this handler and link it to a bot message.

        !!! note
            Calling this multiple times will replace the previously registered message.

        Parameters
        ----------
        rest
            Rest client to use to make the response.
        channel_id
            ID of the channel to respond in.
        add_reactions
            Whether this should add the paginator's reactions to the message
            after responding.
        max_retries
            How many times this should retry to respond if Hikari raises
            any ratelimit errors.
        max_backoff
            The maximum time this should backoff for before trying if Hikari
            raises any ratelimit errors.

        Returns
        -------
        hikari.messages.Message
            Object of the message this handler now targets.
            If `message` was not supplied then this will be the object of a newly created
            message, otherwise this will be what was supplied as `message`.

        Raises
        ------
        ValueError
            If the provided iterator didn't yield any content for the first message.
        """
        if self._message is not None:
            raise RuntimeError("ReactionPaginator is already running")

        retry = backoff.Backoff(max_retries=max_retries - 1, maximum=max_backoff)
        entry = await self.get_next_entry()

        if entry is None:
            raise ValueError("ReactionPaginator iterator yielded no pages.")

        async for _ in retry:
            try:
                message = await rest.create_message(channel_id, content=entry[0], embed=entry[1])

            except hikari.RateLimitedError as exc:
                if exc.retry_after > max_backoff:
                    raise

                retry.set_next_backoff(exc.retry_after)

            except hikari.InternalServerError:
                continue

            else:
                break

        else:
            message = await rest.create_message(channel_id, content=entry[0], embed=entry[1])

        await self.open(message, add_reactions=add_reactions, max_retries=max_retries, max_backoff=max_backoff)
        return message


class ReactionClient:
    """A class which handles the events for multiple registered reaction handlers.

    !!! note
        For a quicker way to initialise this client from a bot, see
        [yuyo.reactions.ReactionClient.from_gateway_bot][].
    """

    __slots__ = ("_alluka", "blacklist", "_event_manager", "_gc_task", "_handlers", "_rest")

    def __init__(
        self,
        *,
        rest: hikari.api.RESTClient,
        event_manager: hikari.api.EventManager,
        alluka: typing.Optional[alluka_.abc.Client] = None,
        event_managed: bool = True,
    ) -> None:
        """Initialise a reaction client.

        Parameters
        ----------
        rest
            The REST client to register this reaction client with.
        event_manager
            The event manager client to register this reaction client with.
        alluka
            The alluka client to use for callback DI.
        event_managed
            Whether the reaction client should be automatically opened and
            closed based on the lifetime events dispatched by `event_managed`.
        """
        self._alluka = alluka or alluka_.Client()
        self.blacklist: typing.List[hikari.Snowflake] = []
        self._event_manager = event_manager
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._handlers: typing.Dict[hikari.Snowflake, AbstractReactionHandler] = {}
        self._rest = rest

        if event_managed:
            self._event_manager.subscribe(hikari.StartingEvent, self._on_starting_event)
            self._event_manager.subscribe(hikari.StoppingEvent, self._on_stopping_event)

    @property
    def alluka(self) -> alluka_.abc.Client:
        """The Alluka client being used for callback dependency injection."""
        return self._alluka

    @classmethod
    def from_gateway_bot(cls, bot: traits.GatewayBotAware, /, *, event_managed: bool = True) -> ReactionClient:
        """Build a `ReactionClient` from a gateway bot.

        Parameters
        ----------
        bot
            The bot to build a reaction client for.
        event_managed
            Whether the reaction client should be automatically opened and
            closed based on the lifetime events dispatched by `bot`.

        Returns
        -------
        ReactionClient
            The reaction client for the bot.
        """
        return cls(rest=bot.rest, event_manager=bot.event_manager, event_managed=event_managed)

    async def _gc(self) -> None:
        while True:
            for listener_id, listener in tuple(self._handlers.items()):
                if not listener.has_expired or listener_id not in self._handlers:
                    continue

                del self._handlers[listener_id]
                # This may slow this gc task down but the more we yield the better.
                await listener.close()

            await asyncio.sleep(5)  # TODO: is this a good time?

    async def _on_reaction_event(
        self, event: typing.Union[hikari.ReactionAddEvent, hikari.ReactionDeleteEvent], /
    ) -> None:
        if event.user_id in self.blacklist:
            return

        if listener := self._handlers.get(event.message_id):
            try:
                await listener.on_reaction_event(event, alluka=self._alluka)
            except HandlerClosed:
                self._handlers.pop(event.message_id, None)

    async def _on_starting_event(self, _: hikari.StartingEvent, /) -> None:
        await self.open()

    async def _on_stopping_event(self, _: hikari.StoppingEvent, /) -> None:
        await self.close()

    @property
    def is_closed(self) -> bool:
        """Whether this client is closed."""
        return self._gc_task is None

    def add_handler(
        self,
        message: hikari.SnowflakeishOr[hikari.Message],
        /,
        paginator: AbstractReactionHandler,
    ) -> Self:
        """Add a reaction handler to this reaction client.

        !!! note
            This does not call [yuyo.reactions.AbstractReactionHandler.open][].

        Parameters
        ----------
        message
            The message ID to add register a reaction handler with.
        paginator
            The object of the opened paginator to register in this reaction client.
        """
        self._handlers[hikari.Snowflake(message)] = paginator
        return self

    def get_handler(
        self, message: hikari.SnowflakeishOr[hikari.Message], /
    ) -> typing.Optional[AbstractReactionHandler]:
        """Get a reference to a paginator registered in this reaction client.

        !!! note
            This does not call [yuyo.reactions.AbstractReactionHandler.close][].

        Parameters
        ----------
        message
            The message ID to remove a paginator for.

        Returns
        -------
        AbstractReactionHandler | None
            The object of the registered paginator if found else [None][].
        """
        return self._handlers.get(hikari.Snowflake(message))

    def remove_handler(
        self, message: hikari.SnowflakeishOr[hikari.Message], /
    ) -> typing.Optional[AbstractReactionHandler]:
        """Remove a paginator from this reaction client.

        !!! note
            This does not call [yuyo.reactions.AbstractReactionHandler.close][].

        Parameters
        ----------
        message
            The message ID to remove a paginator for.

        Returns
        -------
        AbstractReactionHandler | None
            The object of the registered paginator if found else [None][].
        """
        return self._handlers.pop(hikari.Snowflake(message))

    def _try_unsubscribe(
        self,
        event_type: typing.Type[_EventT],
        callback: event_manager_api.CallbackT[_EventT],
    ) -> None:
        try:
            self._event_manager.unsubscribe(event_type, callback)
        except (ValueError, LookupError):
            # TODO: add logging here
            pass

    async def close(self) -> None:
        """Close this client by unregistering any registered tasks and event listeners."""
        if self._gc_task is not None:
            self._try_unsubscribe(hikari.ReactionAddEvent, self._on_reaction_event)
            self._try_unsubscribe(hikari.ReactionDeleteEvent, self._on_reaction_event)
            self._gc_task.cancel()
            listeners = self._handlers
            self._handlers = {}
            await asyncio.gather(*(listener.close() for listener in listeners.values()))

    async def open(self) -> None:
        """Start this client by registering the required tasks and event listeners for it to function."""
        if self._gc_task is None:
            self._gc_task = asyncio.create_task(self._gc())
            self.blacklist.append((await self._rest.fetch_my_user()).id)
            self._event_manager.subscribe(hikari.ReactionAddEvent, self._on_reaction_event)
            self._event_manager.subscribe(hikari.ReactionDeleteEvent, self._on_reaction_event)
