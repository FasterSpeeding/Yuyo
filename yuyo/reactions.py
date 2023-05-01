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
"""Client for higher level callback based reaction menu handling."""

from __future__ import annotations

__all__: list[str] = ["ReactionClient", "ReactionHandler", "ReactionPaginator"]

import abc
import asyncio
import datetime
import typing
from collections import abc as collections

import alluka as alluka_
import hikari

from . import _internal
from . import pagination
from . import timeouts

if typing.TYPE_CHECKING:
    import tanjun
    from hikari.api import event_manager as event_manager_api
    from typing_extensions import Self

    _CallbackSigT = typing.TypeVar("_CallbackSigT", bound="CallbackSig")
    _EventT = typing.TypeVar("_EventT", bound=hikari.Event)

    # This doesn't enforce ShardAware (unlike yuyo._internal.GatewayBotProto)
    class _GatewayBotProto(hikari.EventManagerAware, hikari.RESTAware, typing.Protocol):
        """Protocol of a cacheless Hikari Gateway bot."""


ReactionEventT = typing.Union[hikari.ReactionAddEvent, hikari.ReactionDeleteEvent]
"""Type hint of the event types [CallbackSig][yuyo.reactions.CallbackSig] takes as its first argument."""

CallbackSig = collections.Callable[..., collections.Coroutine[typing.Any, typing.Any, None]]
"""Type-hint of a callback used to handle matching reactions events."""


class HandlerClosed(Exception):
    """Error raised when a reaction handler has been closed."""


class AbstractReactionHandler(abc.ABC):
    """The interface for a reaction handler used with [yuyo.reactions.ReactionClient][]."""

    __slots__ = ()

    @property
    @abc.abstractmethod
    def has_expired(self) -> bool:
        """Whether this handler has ended."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Close this handler."""

    @abc.abstractmethod
    async def open(self, message: hikari.Message, /) -> None:
        """Open this handler.

        Parameters
        ----------
        message
            The message to bind this handler to.
        """

    @abc.abstractmethod
    async def on_reaction_event(
        self, event: ReactionEventT, /, *, alluka: typing.Optional[alluka_.abc.Client] = None
    ) -> None:
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


class ReactionHandler(AbstractReactionHandler):
    """Standard basic implementation of a reaction handler."""

    __slots__ = ("_authors", "_callbacks", "_last_triggered", "_lock", "_message", "_timeout")

    def __init__(
        self,
        *,
        authors: collections.Iterable[hikari.SnowflakeishOr[hikari.User]] = (),
        timeout: typing.Optional[datetime.timedelta] = datetime.timedelta(seconds=30),
    ) -> None:
        """Initialise a reaction handler.

        Parameters
        ----------
        authors
            An iterable of IDs of the users who can call this handler.

            If no users are provided then the reactions will be public (meaning
            that anybody can use it).
        timeout
            How long it should take for this handler to timeout.
        """
        self._authors = set(map(hikari.Snowflake, authors))
        self._callbacks: dict[typing.Union[str, int], CallbackSig] = {}
        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        self._lock = asyncio.Lock()
        self._message: typing.Optional[hikari.Message] = None

        if timeout is None:
            self._timeout: timeouts.AbstractTimeout = timeouts.NeverTimeout()

        else:
            self._timeout = timeouts.SlidingTimeout(timeout, max_uses=-1)

    @property
    def authors(self) -> collections.Set[hikari.Snowflake]:
        """Set of the authors/owner of a enabled handler.

        !!! note
            If this is empty then the handler is considered public and
            any user will be able to trigger it.
        """
        # Pyright bug
        return frozenset(self._authors)  # pyright: ignore[reportGeneralTypeIssues]

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractReactionHandler>>.
        return self._timeout.has_expired

    async def open(self, message: hikari.Message, /) -> None:
        self._message = message

    async def close(self) -> None:
        # <<inherited docstring from AbstractReactionHandler>>.
        self._message = None

    def set_callback(
        self, emoji_identifier: typing.Union[str, hikari.SnowflakeishOr[hikari.CustomEmoji]], callback: CallbackSig, /
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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        """Add a callback to this reaction handler through a decorator call.

        Parameters
        ----------
        emoji_identifier
            Identifier of the emoji this callback is for.

            This should be a snowfake if this is for a custom emoji or a string
            if this is for a unicode emoji.

        Returns
        -------
        collections.abc.Callback[[CallbackSig], CallbackSig]
            A decorator to add a callback to this reaction handler.
        """

        def decorator(callback: _CallbackSigT, /) -> _CallbackSigT:
            nonlocal emoji_identifier
            if isinstance(emoji_identifier, hikari.CustomEmoji):
                emoji_identifier = emoji_identifier.id

            self.set_callback(emoji_identifier, callback)
            return callback

        return decorator

    async def on_reaction_event(
        self, event: ReactionEventT, /, *, alluka: typing.Optional[alluka_.abc.Client] = None
    ) -> None:
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


Handler = ReactionHandler
"""Alias of [ReactionHandler][yuyo.reactions.ReactionHandler]."""


class ReactionPaginator(ReactionHandler):
    """Standard implementation of a reaction handler for pagination."""

    __slots__ = ("_paginator", "_reactions")

    def __init__(
        self,
        iterator: _internal.IteratorT[pagination.EntryT],
        /,
        *,
        authors: collections.Iterable[hikari.SnowflakeishOr[hikari.User]] = (),
        triggers: collections.Collection[str] = (
            pagination.LEFT_TRIANGLE,
            pagination.STOP_SQUARE,
            pagination.RIGHT_TRIANGLE,
        ),
        timeout: typing.Optional[datetime.timedelta] = datetime.timedelta(seconds=30),
    ) -> None:
        """Initialise a reaction paginator.

        Parameters
        ----------
        iterator : collections.Iterator[yuyo.pagination.EntryT] | collections.AsyncIterator[yuyo.pagination.EntryT]
            Either an asynchronous or synchronous iterator of the entries this
            should paginate through.

            This should be an iterator of [yuyo.pagination.Page][]s.
        authors
            An iterable of IDs of the users who can call this paginator.

            If no users are provided then the reactions will be public (meaning
            that anybody can use it).
        timeout
            How long it should take for this paginator to timeout.
        """
        if not isinstance(
            iterator, (collections.Iterator, collections.AsyncIterator)
        ):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"Invalid value passed for `iterator`, expected an iterator but got {type(iterator)}")

        super().__init__(authors=authors, timeout=timeout)
        self._paginator = pagination.Paginator(iterator)
        self._reactions: list[typing.Union[hikari.CustomEmoji, str]] = []

        if pagination.LEFT_DOUBLE_TRIANGLE in triggers:
            self.add_first_button()

        if pagination.LEFT_TRIANGLE in triggers:
            self.add_previous_button()

        if pagination.STOP_SQUARE in triggers or pagination.BLACK_CROSS in triggers:
            self.add_stop_button()

        if pagination.RIGHT_TRIANGLE in triggers:
            self.add_next_button()

        if pagination.RIGHT_DOUBLE_TRIANGLE in triggers:
            self.add_last_button()

    def _add_button(
        self, callback: CallbackSig, emoji: typing.Union[hikari.CustomEmoji, str], add_reaction: bool, /
    ) -> Self:
        self.set_callback(emoji, callback)

        if add_reaction:
            self._reactions.append(emoji)

        return self

    def add_first_button(
        self,
        *,
        emoji: typing.Union[hikari.CustomEmoji, str] = pagination.LEFT_DOUBLE_TRIANGLE,
        add_reaction: bool = True,
    ) -> Self:
        r"""Add the jump to first entry reaction button to this paginator.

        You should pass `triggers=[]` to
        [yuyo.reactions.ReactionPaginator.__init__][ComponentPaginator.\_\_init\_\_]
        before calling this.

        !!! note
            These reactions will appear in the order these methods were called in.

        Parameters
        ----------
        emoji
            The emoji to react with for this button.
        add_reaction
            Whether the bot should add this reaction to the message when
            [ReactionPaginator.open][yuyo.reactions.ReactionPaginator.open] is
            called with `add_reactions=True`.

        Returns
        -------
        Self
            To enable chained calls.
        """
        return self._add_button(self._on_first, emoji, add_reaction)

    def add_previous_button(
        self, *, emoji: typing.Union[hikari.CustomEmoji, str] = pagination.LEFT_TRIANGLE, add_reaction: bool = True
    ) -> Self:
        r"""Add the previous entry reaction button to this paginator.

        You should pass `triggers=[]` to
        [yuyo.reactions.ReactionPaginator.__init__][ComponentPaginator.\_\_init\_\_]
        before calling this.

        !!! note
            These reactions will appear in the order these methods were called in.

        Parameters
        ----------
        emoji
            The emoji to react with for this button.
        add_reaction
            Whether the bot should add this reaction to the message when
            [ReactionPaginator.open][yuyo.reactions.ReactionPaginator.open] is
            called with `add_reactions=True`.

        Returns
        -------
        Self
            To enable chained calls.
        """
        return self._add_button(self._on_previous, emoji, add_reaction)

    def add_stop_button(
        self, *, emoji: typing.Union[hikari.CustomEmoji, str] = pagination.STOP_SQUARE, add_reaction: bool = True
    ) -> Self:
        r"""Add the stop reaction button to this paginator.

        You should pass `triggers=[]` to
        [yuyo.reactions.ReactionPaginator.__init__][ComponentPaginator.\_\_init\_\_]
        before calling this.

        !!! note
            These reactions will appear in the order these methods were called in.

        Parameters
        ----------
        emoji
            The emoji to react with for this button.
        add_reaction
            Whether the bot should add this reaction to the message when
            [ReactionPaginator.open][yuyo.reactions.ReactionPaginator.open] is
            called with `add_reactions=True`.

        Returns
        -------
        Self
            To enable chained calls.
        """
        return self._add_button(self._on_disable, emoji, add_reaction)

    def add_next_button(
        self, *, emoji: typing.Union[hikari.CustomEmoji, str] = pagination.RIGHT_TRIANGLE, add_reaction: bool = True
    ) -> Self:
        r"""Add the next entry reaction button to this paginator.

        You should pass `triggers=[]` to
        [yuyo.reactions.ReactionPaginator.__init__][ComponentPaginator.\_\_init\_\_]
        before calling this.

        !!! note
            These reactions will appear in the order these methods were called in.

        Parameters
        ----------
        emoji
            The emoji to react with for this button.
        add_reaction
            Whether the bot should add this reaction to the message when
            [ReactionPaginator.open][yuyo.reactions.ReactionPaginator.open] is
            called with `add_reactions=True`.

        Returns
        -------
        Self
            To enable chained calls.
        """
        return self._add_button(self._on_next, emoji, add_reaction)

    def add_last_button(
        self,
        *,
        emoji: typing.Union[hikari.CustomEmoji, str] = pagination.RIGHT_DOUBLE_TRIANGLE,
        add_reaction: bool = True,
    ) -> Self:
        r"""Add the jump to last entry reaction button to this paginator.

        You should pass `triggers=[]` to
        [yuyo.reactions.ReactionPaginator.__init__][ComponentPaginator.\_\_init\_\_]
        before calling this.

        !!! note
            These reactions will appear in the order these methods were called in.

        Parameters
        ----------
        emoji
            The emoji to react with for this button.
        add_reaction
            Whether the bot should add this reaction to the message when
            [ReactionPaginator.open][yuyo.reactions.ReactionPaginator.open] is
            called with `add_reactions=True`.

        Returns
        -------
        Self
            To enable chained calls.
        """
        return self._add_button(self._on_last, emoji, add_reaction)

    async def _edit_message(self, response: pagination.Page, /) -> None:
        if self._message is None:
            return

        try:
            await self._message.edit(**response.to_kwargs())

        except (hikari.NotFoundError, hikari.ForbiddenError) as exc:
            raise HandlerClosed() from exc

    async def _on_disable(self, _: ReactionEventT, /) -> None:
        self._paginator.close()
        if message := self._message:
            self._message = None
            # We create a task here rather than awaiting this to ensure the instance is marked as ended as soon as
            # possible.
            asyncio.create_task(message.delete())

        raise HandlerClosed

    async def _on_first(self, _: ReactionEventT, /) -> None:
        if page := self._paginator.jump_to_first():
            await self._edit_message(page)

    async def _on_last(self, _: ReactionEventT, /) -> None:
        if page := await self._paginator.jump_to_last():
            await self._edit_message(page)

    async def get_next_entry(self) -> typing.Optional[pagination.Page]:
        """Get the next entry in this paginator.

        Returns
        -------
        yuyo.pagination.Page | None
            The next entry in this paginator, or [None][] if there are no more entries.
        """
        return await self._paginator.step_forward()

    async def _on_next(self, _: ReactionEventT, /) -> None:
        if entry := await self._paginator.step_forward():
            await self._edit_message(entry)

    async def _on_previous(self, _: ReactionEventT, /) -> None:
        if entry := self._paginator.step_back():
            await self._edit_message(entry)

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

    async def close(self, *, remove_reactions: bool = False) -> None:
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

            # TODO: check if we can just clear the reactions before doing this using the cache.
            for emoji_name in self._reactions:
                try:
                    await message.remove_reaction(emoji_name)

                except (hikari.NotFoundError, hikari.ForbiddenError):
                    return

    async def open(self, message: hikari.Message, /, *, add_reactions: bool = True) -> None:
        """Start the reaction paginator and start accepting reactions..

        Parameters
        ----------
        message
            The message this paginator should target.
        add_reactions
            Whether this should add the paginator's reactions to the message.
        """
        await super().open(message)
        if not add_reactions:
            return

        for emoji_name in self._reactions:
            try:
                await message.add_reaction(emoji_name)

            except hikari.NotFoundError:
                self._message = None
                raise

            except hikari.ForbiddenError:  # TODO: attempt to check permissions first
                # If this is reached then we just don't have reaction permissions in the channel.
                return

    async def create_message(
        self,
        rest: hikari.api.RESTClient,
        channel_id: hikari.SnowflakeishOr[hikari.TextableChannel],
        /,
        *,
        add_reactions: bool = True,
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

        entry = await self._paginator.step_forward()

        if entry is None:
            raise ValueError("ReactionPaginator iterator yielded no pages.")

        message = await rest.create_message(channel_id, **entry.to_kwargs())
        await self.open(message, add_reactions=add_reactions)
        return message


Paginator = ReactionPaginator
"""Alias of [ReactionPaginator][yuyo.reactions.ReactionPaginator]."""


class ReactionClient:
    """A class which handles the events for multiple registered reaction handlers."""

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

        This registers [ReactionClient][yuyo.reactions.ReactionClient] as a type
        dependency when `alluka` isn't passed.

        !!! note
            For an easier way to initialise the client from a bot see
            [ReactionClient.from_gateway_bot][yuyo.reactions.ReactionClient.from_gateway_bot],
            and [ReactionClient.from_tanjun][yuyo.reactions.ReactionClient.from_tanjun].

        Parameters
        ----------
        rest
            The REST client to register this reaction client with.
        event_manager
            The event manager client to register this reaction client with.
        alluka
            The Alluka client to use for callback dependency injection in this client.

            If not provided then this will initialise its own Alluka client.
        event_managed
            Whether the reaction client should be automatically opened and
            closed based on the lifetime events dispatched by `event_managed`.
        """
        if alluka is None:
            alluka = alluka_.Client()
            self._set_standard_deps(alluka)

        self._alluka = alluka
        self.blacklist: list[hikari.Snowflake] = []
        self._event_manager = event_manager
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._handlers: dict[hikari.Snowflake, AbstractReactionHandler] = {}
        self._rest = rest

        if event_managed:
            self._event_manager.subscribe(hikari.StartingEvent, self._on_starting_event)
            self._event_manager.subscribe(hikari.StoppingEvent, self._on_stopping_event)

    @property
    def alluka(self) -> alluka_.abc.Client:
        """The Alluka client being used for callback dependency injection."""
        return self._alluka

    @classmethod
    def from_gateway_bot(
        cls, bot: _GatewayBotProto, /, *, alluka: typing.Optional[alluka_.abc.Client] = None, event_managed: bool = True
    ) -> Self:
        """Build a `ReactionClient` from a gateway bot.

        This registers [ReactionClient][yuyo.reactions.ReactionClient] as a type
        dependency when `alluka` isn't passed.

        Parameters
        ----------
        bot : hikari.traits.EventManagerAware & hikari.traits.RESTAware
            The bot to build a reaction client for.
        alluka
            The Alluka client to use for callback dependency injection in this client.

            If not provided then this will initialise its own Alluka client.
        event_managed
            Whether the reaction client should be automatically opened and
            closed based on the lifetime events dispatched by `bot`.

        Returns
        -------
        ReactionClient
            The reaction client for the bot.
        """
        return cls(alluka=alluka, rest=bot.rest, event_manager=bot.event_manager, event_managed=event_managed)

    @classmethod
    def from_tanjun(cls, tanjun_client: tanjun.abc.Client, /, *, tanjun_managed: bool = True) -> Self:
        """Build a `ReactionClient` from a gateway bot.

        This will use the Tanjun client's alluka client and registers
        [ReactionClient][yuyo.reactions.ReactionClient] as a type dependency on
        Tanjun.

        Parameters
        ----------
        tanjun_client
            The tanjun client to build a reaction client for.
        tanjun_managed
            Whether the reaction client should be automatically opened and
            closed based on the Tanjun client's lifetime client callback.

        Returns
        -------
        ReactionClient
            The reaction client for the bot.

        Raises
        ------
        ValueError
            If [tanjun.abc.Client.events][] is [None][].
        """
        import tanjun

        if not tanjun_client.events:
            raise ValueError("Cannot build from a tanjun client with no event manager")

        self = cls(alluka=tanjun_client.injector, rest=tanjun_client.rest, event_manager=tanjun_client.events)
        self._set_standard_deps(tanjun_client.injector)

        if tanjun_managed:
            tanjun_client.add_client_callback(tanjun.ClientCallbackNames.STARTING, self.open)
            tanjun_client.add_client_callback(tanjun.ClientCallbackNames.CLOSING, self.close)

        return self

    def _set_standard_deps(self, alluka: alluka_.abc.Client) -> None:
        alluka.set_type_dependency(ReactionClient, self)

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

    def set_handler(self, message: hikari.SnowflakeishOr[hikari.Message], handler: AbstractReactionHandler, /) -> Self:
        """Add a reaction handler to this reaction client.

        !!! note
            This does not call [yuyo.reactions.AbstractReactionHandler.open][].

        Parameters
        ----------
        message
            The message ID to add register a reaction handler with.
        handler
            The object of the opened handler to register in this reaction client.
        """
        self._handlers[hikari.Snowflake(message)] = handler
        return self

    def get_handler(
        self, message: hikari.SnowflakeishOr[hikari.Message], /
    ) -> typing.Optional[AbstractReactionHandler]:
        """Get a reference to a handler registered in this reaction client.

        !!! note
            This does not call [yuyo.reactions.AbstractReactionHandler.close][].

        Parameters
        ----------
        message
            The message ID to remove a handler for.

        Returns
        -------
        AbstractReactionHandler | None
            The object of the registered handler if found else [None][].
        """
        return self._handlers.get(hikari.Snowflake(message))

    def remove_handler(
        self, message: hikari.SnowflakeishOr[hikari.Message], /
    ) -> typing.Optional[AbstractReactionHandler]:
        """Remove a handler from this reaction client.

        !!! note
            This does not call [yuyo.reactions.AbstractReactionHandler.close][].

        Parameters
        ----------
        message
            The message ID to remove a handler for.

        Returns
        -------
        AbstractReactionHandler | None
            The object of the registered handler if found else [None][].
        """
        return self._handlers.pop(hikari.Snowflake(message))

    def _try_unsubscribe(self, event_type: type[_EventT], callback: event_manager_api.CallbackT[_EventT], /) -> None:
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


Client = ReactionClient
"""Alias of [ReactionClient][yuyo.reactions.ReactionClient]."""
