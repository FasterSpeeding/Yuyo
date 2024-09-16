# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Copyright (c) 2020-2024, Faster Speeding
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notfice, this
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
"""Higher level client for callback based component execution."""
from __future__ import annotations

__all__: list[str] = [
    "ActionColumnExecutor",
    "ComponentClient",
    "ComponentContext",
    "ComponentExecutor",
    "ComponentPaginator",
    "StaticComponentPaginator",
    "StaticPaginatorIndex",
    "StreamExecutor",
    "WaitForExecutor",
    "as_channel_menu",
    "as_interactive_button",
    "as_mentionable_menu",
    "as_role_menu",
    "as_select_menu",
    "as_text_menu",
    "as_user_menu",
    "builder",
    "column_template",
    "link_button",
    "with_option",
]

import abc
import asyncio
import base64
import copy
import dataclasses
import datetime
import enum
import functools
import hashlib
import itertools
import types
import typing
import urllib.parse
from collections import abc as collections

import alluka
import alluka as alluka_
import alluka.local as alluka_local
import hikari
import typing_extensions

from . import _internal
from . import interactions
from . import modals
from . import pagination
from . import timeouts
from ._internal import localise

_T = typing.TypeVar("_T")

if typing.TYPE_CHECKING:
    import tanjun
    from typing_extensions import Self

    _OtherT = typing.TypeVar("_OtherT")
    _TextMenuT = typing.TypeVar(
        "_TextMenuT", "_TextMenuDescriptor[typing.Any, typing.Any]", "_WrappedTextMenuBuilder[...]"
    )

    class _GatewayBotProto(hikari.RESTAware, hikari.ShardAware, hikari.EventManagerAware, typing.Protocol):
        """Trait of a cacheless gateway bot."""


_P = typing_extensions.ParamSpec("_P")
_CoroT = collections.Coroutine[typing.Any, typing.Any, None]
_SelfT = typing.TypeVar("_SelfT")

_ComponentResponseT = typing.Union[
    hikari.api.InteractionMessageBuilder, hikari.api.InteractionDeferredBuilder, hikari.api.InteractionModalBuilder
]
"""Type hint of the builder response types allows for component interactions."""

CallbackSig = collections.Callable[..., collections.Coroutine[typing.Any, typing.Any, None]]
"""Type hint of a component callback."""

_CallbackSigT = typing.TypeVar("_CallbackSigT", bound=CallbackSig)


def _now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def _consume(
    value: typing.Optional[_T], callback: collections.Callable[[_T], _OtherT], /
) -> typing.Union[_OtherT, collections.Callable[[_T], _OtherT]]:
    if value is not None:
        return callback(value)

    return callback


def _decorate(
    value: typing.Optional[_T], callback: collections.Callable[[_T], object], /
) -> typing.Union[_T, collections.Callable[[_T], _T]]:
    def decorator(value_: _T) -> _T:
        callback(value_)
        return value_

    return _consume(value, decorator)


class ComponentContext(interactions.BaseContext[hikari.ComponentInteraction]):
    """The context used for message component triggers."""

    __slots__ = ("_client",)

    def __init__(
        self,
        client: Client,
        interaction: hikari.ComponentInteraction,
        id_match: str,
        id_metadata: str,
        register_task: collections.Callable[[asyncio.Task[typing.Any]], None],
        *,
        ephemeral_default: bool = False,
        response_future: typing.Optional[asyncio.Future[_ComponentResponseT]] = None,
    ) -> None:
        super().__init__(
            interaction=interaction,
            id_match=id_match,
            id_metadata=id_metadata,
            register_task=register_task,
            ephemeral_default=ephemeral_default,
            response_future=response_future,
        )
        self._client = client
        self._response_future = response_future

    @property
    def alluka(self) -> alluka_.abc.Client:
        """The Alluka client being used for callback dependency injection."""
        return self._client.alluka

    @property
    def selected_channels(self) -> collections.Mapping[hikari.Snowflake, hikari.InteractionChannel]:
        """Sequence of the users passed for a channel select menu."""
        if not self.interaction.resolved:
            return {}

        return self.interaction.resolved.channels

    @property
    def selected_roles(self) -> collections.Mapping[hikari.Snowflake, hikari.Role]:
        """Sequence of the users passed for a role select menu.

        This will also include some of the values for a mentionable select menu.
        """
        if not self.interaction.resolved:
            return {}

        return self.interaction.resolved.roles

    @property
    def selected_texts(self) -> collections.Sequence[str]:
        """Sequence of the values passed for a text select menu."""
        return self._interaction.values

    @property
    def selected_users(self) -> collections.Mapping[hikari.Snowflake, hikari.User]:
        """Sequence of the users passed for a user select menu.

        This will also include some of the values for a mentionable select menu.

        [ComponentContext.selected_members][yuyo.components.ComponentContext.selected_members]
        has the full member objects.
        """
        if not self.interaction.resolved:
            return {}

        return self.interaction.resolved.users

    @property
    def selected_members(self) -> collections.Mapping[hikari.Snowflake, hikari.InteractionMember]:
        """Sequence of the members passed for a user select menu.

        This will also include some of the values for a mentionable select menu.
        """
        if not self.interaction.resolved:
            return {}

        return self.interaction.resolved.members

    @property
    def cache(self) -> typing.Optional[hikari.api.Cache]:
        """Hikari cache instance this context's client was initialised with."""
        return self._client.cache

    @property
    def client(self) -> Client:
        """The component client this context is bound to."""
        return self._client

    @property
    def events(self) -> typing.Optional[hikari.api.EventManager]:
        """Object of the event manager this context's client was initialised with."""
        return self._client.events

    @property
    def rest(self) -> typing.Optional[hikari.api.RESTClient]:
        """Object of the Hikari REST client this context's client was initialised with."""
        return self._client.rest

    @property
    def server(self) -> typing.Optional[hikari.api.InteractionServer]:
        """Object of the Hikari interaction server provided for this context's client."""
        return self._client.server

    @property
    def shards(self) -> typing.Optional[hikari.ShardAware]:
        """Object of the Hikari shard manager this context's client was initialised with."""
        return self._client.shards

    @property
    def voice(self) -> typing.Optional[hikari.api.VoiceComponent]:
        """Object of the Hikari voice component this context's client was initialised with."""
        return self._client.voice

    async def create_modal_response(
        self,
        title: str,
        custom_id: str,
        /,
        *,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[collections.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
    ) -> typing.Optional[WaitFor]:
        """Send a modal as the initial response for this context.

        !!! warning
            This must be called as the first response to a context before any
            deferring.

        Parameters
        ----------
        title
            The title that will show up in the modal.
        custom_id
            Developer set custom ID used for identifying interactions with this modal.

            Yuyo's Component client will only match against `custom_id.split(":", 1)[0]`,
            allowing metadata to be put after `":"`.
        component
            A component builder to send in this modal.
        components
            A sequence of component builders to send in this modal.

        Raises
        ------
        ValueError
            If both `component` and `components` are specified or if none are specified.
        hikari.errors.BadRequestError
            When the requests' data is outside Discord's accept ranges/validation.
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.NotFoundError
            If the interaction is not found or if the interaction's initial
            response has already been created or deferred.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        async with self._response_lock:
            if self._has_responded or self._has_been_deferred:
                raise RuntimeError("Initial response has already been created")

            if self._response_future:
                components, _ = _internal.to_list(component, components, None, hikari.api.ComponentBuilder, "component")

                response = hikari.impl.InteractionModalBuilder(title, custom_id, components or [])
                self._response_future.set_result(response)

            else:
                await self._interaction.create_modal_response(
                    title, custom_id, component=component, components=components
                )

            self._has_responded = True


Context = ComponentContext
"""Alias of [ComponentContext][yuyo.components.ComponentContext]."""


def _gc_executors(executors: dict[typing.Any, tuple[timeouts.AbstractTimeout, AbstractComponentExecutor]]) -> None:
    for key, (timeout, _) in tuple(executors.items()):
        if timeout.has_expired:
            try:
                del executors[key]
                # This may slow this gc task down but the more we yield the better.
                # await executor.close()  # TODO: this

            except KeyError:
                pass


class ExecutorClosed(Exception):
    """Error used to indicate that an executor is now closed during execution."""

    def __init__(self, *, already_closed: bool = True) -> None:
        """Initialise an executor closed error.

        Parameters
        ----------
        already_closed
            Whether this error is a result of the executor having been in a
            closed state when it was called.

            If so then this will lead to a "timed-out" message being sent
            as the initial response.
        """
        self.was_already_closed: bool = already_closed


class ComponentClient:
    """Client used to handle component executors within a REST or gateway flow."""

    __slots__ = (
        "_alluka",
        "_cache",
        "_event_manager",
        "_executors",
        "_gc_task",
        "_message_executors",
        "_rest",
        "_server",
        "_shards",
        "_tasks",
        "_voice",
    )

    def __init__(
        self,
        *,
        alluka: typing.Optional[alluka_.abc.Client] = None,
        cache: typing.Optional[hikari.api.Cache] = None,
        event_manager: typing.Optional[hikari.api.EventManager] = None,
        event_managed: typing.Optional[bool] = None,
        rest: typing.Optional[hikari.api.RESTClient] = None,
        server: typing.Optional[hikari.api.InteractionServer] = None,
        shards: typing.Optional[hikari.ShardAware] = None,
        voice: typing.Optional[hikari.api.VoiceComponent] = None,
    ) -> None:
        """Initialise a component client.

        This sets [ComponentClient][yuyo.components.ComponentClient] as a
        type dependency when `alluka` isn't passed.

        !!! note
            For an easier way to initialise the client from a bot see
            [ComponentClient.from_gateway_bot][yuyo.components.ComponentClient.from_gateway_bot],
            [ComponentClient.from_rest_bot][yuyo.components.ComponentClient.from_rest_bot], and
            [ComponentClient.from_tanjun][yuyo.components.ComponentClient.from_tanjun].

        Parameters
        ----------
        alluka
            The Alluka client to use for callback dependency injection in this client.

            If not provided then this will initialise its own Alluka client.
        event_manager
            The event manager this client should listen to dispatched component
            interactions from if applicable.
        event_managed
            Whether this client should be automatically opened and closed based on
            the lifetime events dispatched by `event_manager`.

            Defaults to [True][] if an event manager is passed.
        server
            The server this client should listen to component interactions
            from if applicable.

        Raises
        ------
        ValueError
            If `event_managed` is passed as [True][] when `event_manager` is [None][].
        """
        if alluka is None:
            alluka = alluka_local.get(default=None) or alluka_.Client()
            self._set_standard_deps(alluka)

        self._alluka = alluka

        self._cache = cache
        self._executors: dict[str, tuple[timeouts.AbstractTimeout, AbstractComponentExecutor]] = {}
        """Dict of custom IDs to executors."""

        self._event_manager = event_manager
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._message_executors: dict[hikari.Snowflake, tuple[timeouts.AbstractTimeout, AbstractComponentExecutor]] = {}
        """Dict of message IDs to executors."""

        self._rest = rest
        self._server = server
        self._shards = shards
        self._tasks: list[asyncio.Task[typing.Any]] = []
        self._voice = voice

        if event_managed or event_managed is None and event_manager:
            if not event_manager:
                raise ValueError("event_managed may only be passed when an event_manager is also passed")

            event_manager.subscribe(hikari.StartingEvent, self._on_starting)
            event_manager.subscribe(hikari.StoppingEvent, self._on_stopping)

    def __enter__(self) -> None:
        self.open()

    def __exit__(
        self,
        _: typing.Optional[type[BaseException]],
        __: typing.Optional[BaseException],
        ___: typing.Optional[types.TracebackType],
    ) -> None:
        self.close()

    @property
    def alluka(self) -> alluka_.abc.Client:
        """The Alluka client being used for callback dependency injection."""
        return self._alluka

    @property
    def cache(self) -> typing.Optional[hikari.api.Cache]:
        """Hikari cache instance this client was initialised with."""
        return self._cache

    @property
    def events(self) -> typing.Optional[hikari.api.EventManager]:
        """Object of the event manager this client was initialised with."""
        return self._event_manager

    @property
    def rest(self) -> typing.Optional[hikari.api.RESTClient]:
        """Object of the Hikari REST client this client was initialised with."""
        return self._rest

    @property
    def server(self) -> typing.Optional[hikari.api.InteractionServer]:
        """Object of the Hikari interaction server provided for this client."""
        return self._server

    @property
    def shards(self) -> typing.Optional[hikari.ShardAware]:
        """Object of the Hikari shard manager this client was initialised with."""
        return self._shards

    @property
    def voice(self) -> typing.Optional[hikari.api.VoiceComponent]:
        """Object of the Hikari voice component this client was initialised with."""
        return self._voice

    @classmethod
    def from_gateway_bot(
        cls, bot: _GatewayBotProto, /, *, alluka: typing.Optional[alluka_.abc.Client] = None, event_managed: bool = True
    ) -> Self:
        """Build a component client from a Gateway Bot.

        This sets [ComponentClient][yuyo.components.ComponentClient] as a
        type dependency when `alluka` isn't passed.

        Parameters
        ----------
        bot
            The Gateway bot this component client should be bound to.
        alluka
            The Alluka client to use for callback dependency injection in this client.

            If not provided then this will initialise its own Alluka client.
        event_managed
            Whether the component client should be automatically opened and
            closed based on the lifetime events dispatched by `bot`.

        Returns
        -------
        ComponentClient
            The initialised component client.
        """
        cache = None
        if isinstance(bot, hikari.CacheAware):
            cache = bot.cache

        return cls(
            alluka=alluka,
            cache=cache,
            event_manager=bot.event_manager,
            event_managed=event_managed,
            rest=bot.rest,
            shards=bot,
            voice=bot.voice,  # TODO: make voice optional here
        )

    @classmethod
    def from_rest_bot(
        cls,
        bot: hikari.RESTBotAware,
        /,
        *,
        alluka: typing.Optional[alluka_.abc.Client] = None,
        bot_managed: bool = False,
    ) -> Self:
        """Build a component client from a REST Bot.

        This sets [ComponentClient][yuyo.components.ComponentClient] as a
        type dependency when `alluka` isn't passed.

        Parameters
        ----------
        bot
            The REST bot this component client should be bound to.
        alluka
            The Alluka client to use for callback dependency injection in this client.

            If not provided then this will initialise its own Alluka client.
        bot_managed
            Whether the component client should be automatically opened and
            closed based on the Bot's startup and shutdown callbacks.

        Returns
        -------
        ComponentClient
            The initialised component client.
        """
        client = cls(alluka=alluka, rest=bot.rest, server=bot.interaction_server)

        if bot_managed:
            bot.add_startup_callback(client._on_starting)
            bot.add_shutdown_callback(client._on_stopping)

        return client

    @classmethod
    def from_tanjun(cls, tanjun_client: tanjun.abc.Client, /, *, tanjun_managed: bool = True) -> Self:
        """Build a component client from a Tanjun client.

        This will use the Tanjun client's alluka client and registers
        [ComponentClient][yuyo.components.ComponentClient] as a type dependency
        on Tanjun.

        Parameters
        ----------
        tanjun_client
            The Tanjun client this component client should be bound to.
        tanjun_managed
            Whether the component client should be automatically opened and
            closed based on the Tanjun client's lifetime client callback.

        Returns
        -------
        ComponentClient
            The initialised component client.
        """
        import tanjun

        self = cls(
            alluka=tanjun_client.injector,
            cache=tanjun_client.cache,
            event_manager=tanjun_client.events,
            rest=tanjun_client.rest,
            server=tanjun_client.server,
            shards=tanjun_client.shards,
            voice=tanjun_client.voice,
        )
        self._set_standard_deps(tanjun_client.injector)

        if tanjun_managed:
            tanjun_client.add_client_callback(tanjun.ClientCallbackNames.STARTING, self.open)
            tanjun_client.add_client_callback(tanjun.ClientCallbackNames.CLOSING, self.close)

        return self

    def _set_standard_deps(self, alluka: alluka_.abc.Client) -> None:
        alluka.set_type_dependency(Client, self)

    def _remove_task(self, task: asyncio.Task[typing.Any], /) -> None:
        self._tasks.remove(task)

    def _add_task(self, task: asyncio.Task[typing.Any], /) -> None:
        if not task.done():
            self._tasks.append(task)
            task.add_done_callback(self._remove_task)

    async def _on_starting(self, _: typing.Union[hikari.StartingEvent, hikari.RESTBotAware], /) -> None:
        self.open()

    async def _on_stopping(self, _: typing.Union[hikari.StoppingEvent, hikari.RESTBotAware], /) -> None:
        self.close()

    async def _gc(self) -> None:
        while True:
            _gc_executors(self._executors)
            _gc_executors(self._message_executors)
            await asyncio.sleep(5)  # TODO: is this a good time?

    def close(self) -> None:
        """Close the component client."""
        if not self._gc_task:
            return

        self._gc_task.cancel()
        self._gc_task = None
        if self._server:
            self._server.set_listener(hikari.ComponentInteraction, None)

        if self._event_manager:
            self._event_manager.unsubscribe(hikari.InteractionCreateEvent, self.on_gateway_event)

        self._executors = {}
        self._message_executors = {}
        # TODO: have the executors be runnable and close them here?

    def open(self) -> None:
        """Startup the component client."""
        if self._gc_task:
            return

        self._gc_task = asyncio.get_running_loop().create_task(self._gc())

        if self._server:
            self._server.set_listener(hikari.ComponentInteraction, self.on_rest_request)

        if self._event_manager:
            self._event_manager.subscribe(hikari.InteractionCreateEvent, self.on_gateway_event)

    async def _execute(
        self,
        remove_from: dict[_T, tuple[timeouts.AbstractTimeout, AbstractComponentExecutor]],
        key: _T,
        entry: tuple[timeouts.AbstractTimeout, AbstractComponentExecutor],
        interaction: hikari.ComponentInteraction,
        id_match: str,
        id_metadata: str,
        /,
        *,
        future: typing.Optional[asyncio.Future[_ComponentResponseT]] = None,
    ) -> bool:
        timeout, executor = entry
        if timeout.has_expired:
            del remove_from[key]
            if future:
                future.set_exception(ExecutorClosed)

            return False

        ctx = Context(
            client=self,
            interaction=interaction,
            id_match=id_match,
            id_metadata=id_metadata,
            register_task=self._add_task,
            response_future=future,
        )
        if timeout.increment_uses():
            del remove_from[key]

        try:
            await executor.execute(ctx)

        except ExecutorClosed as exc:
            remove_from.pop(key, None)
            if not ctx.has_responded and exc.was_already_closed:
                # TODO: properly handle deferrals and going over the 3 minute mark?
                await ctx.create_initial_response("This message has timed-out.", ephemeral=True)

        except interactions.InteractionError as exc:
            await exc.send(ctx)

        return True

    async def on_gateway_event(self, event: hikari.InteractionCreateEvent, /) -> None:
        """Process an interaction create gateway event.

        Parameters
        ----------
        event
            The interaction create gateway event to process.
        """
        if not isinstance(event.interaction, hikari.ComponentInteraction):
            return

        id_match, id_metadata = _internal.split_custom_id(event.interaction.custom_id)
        if entry := self._executors.get(id_match):
            ran = await self._execute(self._executors, id_match, entry, event.interaction, id_match, id_metadata)
            if ran:
                return

        if entry := self._message_executors.get(event.interaction.message.id):
            ran = await self._execute(
                self._message_executors, event.interaction.message.id, entry, event.interaction, id_match, id_metadata
            )
            if ran:
                return

            del self._message_executors[event.interaction.message.id]

        await event.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE, "This message has timed-out.", flags=hikari.MessageFlag.EPHEMERAL
        )

    async def _execute_task(
        self,
        remove_from: dict[_T, tuple[timeouts.AbstractTimeout, AbstractComponentExecutor]],
        key: _T,
        entry: tuple[timeouts.AbstractTimeout, AbstractComponentExecutor],
        interaction: hikari.ComponentInteraction,
        id_match: str,
        id_metadata: str,
        /,
    ) -> typing.Optional[_ComponentResponseT]:
        future: asyncio.Future[_ComponentResponseT] = asyncio.Future()
        self._add_task(
            asyncio.create_task(
                self._execute(remove_from, key, entry, interaction, id_match, id_metadata, future=future)
            )
        )
        try:
            return await future
        except ExecutorClosed:
            return None  # MyPy

    async def on_rest_request(self, interaction: hikari.ComponentInteraction, /) -> _ComponentResponseT:
        """Process a component interaction REST request.

        Parameters
        ----------
        interaction
            The interaction to process.

        Returns
        -------
        ResponseT
            The REST response.
        """
        id_match, id_metadata = _internal.split_custom_id(interaction.custom_id)
        if entry := self._executors.get(id_match):
            result = await self._execute_task(self._executors, id_match, entry, interaction, id_match, id_metadata)
            if result:
                return result

        if entry := self._message_executors.get(interaction.message.id):
            result = await self._execute_task(
                self._message_executors, interaction.message.id, entry, interaction, id_match, id_metadata
            )
            if result:
                return result

        return (
            interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
            .set_content("This message has timed-out.")
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    def register_executor(
        self,
        executor: AbstractComponentExecutor,
        /,
        *,
        message: typing.Optional[hikari.SnowflakeishOr[hikari.Message]] = None,
        timeout: typing.Union[timeouts.AbstractTimeout, None, _internal.NoDefault] = _internal.NO_DEFAULT,
    ) -> Self:
        """Add an executor to this client.

        Parameters
        ----------
        executor
            The executor to register.
        message
            The message to register this executor for.

            If this is left as [None][] then this executor will be registered
            globally for its custom IDs.
        timeout
            The executor's timeout.

            This defaults to a 30 second sliding timeout.

        Returns
        -------
        Self
            The component client to allow chaining.

        Raises
        ------
        ValueError
            If `message` is already registered when it's passed.

            If any of the executor's custom IDs are already registered when
            `message` wasn't passed.
        """
        if timeout is _internal.NO_DEFAULT:
            timeout = timeouts.SlidingTimeout(datetime.timedelta(seconds=30), max_uses=-1)

        elif timeout is None:
            timeout = timeouts.NeverTimeout()

        entry = (timeout, executor)

        if message:
            message = hikari.Snowflake(message)

            if message in self._message_executors:
                raise ValueError("Message already registered")

            self._message_executors[message] = entry

        else:
            if already_registered := self._executors.keys() & executor.custom_ids:
                raise ValueError("The following custom IDs are already registered:", ", ".join(already_registered))

            for custom_id in executor.custom_ids:
                self._executors[custom_id] = entry

        return self

    def get_executor(self, custom_id: str, /) -> typing.Optional[AbstractComponentExecutor]:
        """Get the component executor registered for a custom ID.

        !!! note
            For message scoped executors use
            [get_executor_for_message.][yuyo.components.ComponentClient.get_executor_for_message]
            as they will not be returned here.

        Parameters
        ----------
        custom_id
            The custom ID to get the executor for.

        Returns
        -------
        AbstractComponentExecutor | None
            The executor set for the custom ID or [None][] if none is set.
        """
        if entry := self._executors.get(custom_id):
            return entry[1]

        return None  # MyPy

    def get_executor_for_message(
        self, message: hikari.SnowflakeishOr[hikari.Message], /
    ) -> typing.Optional[AbstractComponentExecutor]:
        """Get the component executor registered for a message.

        Parameters
        ----------
        message
            The message to get the executor for.

        Returns
        -------
        AbstractComponentExecutor | None
            The executor set for the message or [None][] if none is set.
        """
        if entry := self._message_executors.get(hikari.Snowflake(message)):
            return entry[1]

        return None  # MyPy

    def deregister_executor(self, executor: AbstractComponentExecutor, /) -> Self:
        """Remove a component executor by its custom IDs.

        Parameters
        ----------
        executor
            The executor to remove.

        Returns
        -------
        Self
            The component client to allow chaining.

        Raises
        ------
        KeyError
            If the executor isn't registered.
        """
        registered = False
        for custom_id in executor.custom_ids:
            if (entry := self._executors.get(custom_id)) and entry[1] == executor:
                registered = True
                del self._executors[custom_id]

        if not registered:
            raise KeyError("Executor isn't registered")

        return self

    def deregister_message(self, message: hikari.SnowflakeishOr[hikari.Message], /) -> Self:
        """Remove a component executor by its message.

        Parameters
        ----------
        message
            The message to remove the executor for.

        Returns
        -------
        Self
            The component client to allow chaining.

        Raises
        ------
        KeyError
            If the message is not registered.
        """
        del self._message_executors[hikari.Snowflake(message)]
        return self


Client = ComponentClient
"""Alias of [ComponentClient][yuyo.components.ComponentClient]."""


class AbstractComponentExecutor(abc.ABC):
    """Abstract interface of an object which handles the execution of a message component."""

    __slots__ = ()

    @property
    @abc.abstractmethod
    def custom_ids(self) -> collections.Collection[str]:
        """Collection of the custom IDs this executor is listening for."""

    @abc.abstractmethod
    async def execute(self, ctx: Context, /) -> None:
        """Execute this component.

        Parameters
        ----------
        ctx
            The context to execute this with.

        Raises
        ------
        ExecutorClosed
            If the executor is closed.
        """


class SingleExecutor(AbstractComponentExecutor):
    """Component executor with a single callback."""

    __slots__ = ("_callback", "_custom_id", "_ephemeral_default")

    def __init__(self, custom_id: str, callback: CallbackSig, /, *, ephemeral_default: bool = False) -> None:
        """Initialise an executor with a single callback.

        Parameters
        ----------
        custom_id
            The custom ID this executor is triggered for.

            This will be matched against `interaction.custom_id.split(":", 1)[0]`,
            allowing metadata to be stored after a `":"`.
        callback
            The executor's  callback.
        ephemeral_default
            Whether this executor's responses should default to being ephemeral.

        Raises
        ------
        ValueError
            If `":"` is in the custom ID.
        """
        if ":" in custom_id:
            raise ValueError("Custom ID cannot contain `:`")

        self._callback = callback
        self._custom_id = custom_id
        self._ephemeral_default = ephemeral_default

    @property
    def custom_ids(self) -> collections.Collection[str]:
        return [self._custom_id]

    async def execute(self, ctx: Context, /) -> None:
        ctx.set_ephemeral_default(self._ephemeral_default)
        await ctx.client.alluka.call_with_async_di(self._callback, ctx)


def as_single_executor(
    custom_id: str, /, *, ephemeral_default: bool = False
) -> collections.Callable[[CallbackSig], SingleExecutor]:
    """Create an executor with a single callback by decorating the callback.

    Parameters
    ----------
    custom_id
        The custom ID this executor is triggered for.

        This will be matched against `interaction.custom_id.split(":", 1)[0]`,
        allowing metadata to be stored after a `":"`.
    ephemeral_default
        Whether this executor's responses should default to being ephemeral.

    Returns
    -------
    SingleExecutor
        The created executor.
    """
    return lambda callback: SingleExecutor(custom_id, callback, ephemeral_default=ephemeral_default)


class ComponentExecutor(AbstractComponentExecutor):  # TODO: Not found action?
    """implementation of a component executor with per-custom ID callbacks."""

    __slots__ = ("_ephemeral_default", "_id_to_callback")

    def __init__(self, *, ephemeral_default: bool = False) -> None:
        """Initialise a component executor.

        Parameters
        ----------
        ephemeral_default
            Whether this executor's responses should default to being ephemeral.
        """
        self._ephemeral_default = ephemeral_default
        self._id_to_callback: dict[str, CallbackSig] = {}

    @property
    def callbacks(self) -> collections.Mapping[str, CallbackSig]:
        """Mapping of custom IDs to their set callbacks."""
        return self._id_to_callback.copy()

    @property
    def custom_ids(self) -> collections.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._id_to_callback

    async def execute(self, ctx: Context, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        ctx.set_ephemeral_default(self._ephemeral_default)
        callback = self._id_to_callback[ctx.id_match]
        await ctx.client.alluka.call_with_async_di(callback, ctx)

    def set_callback(self, custom_id: str, callback: CallbackSig, /) -> Self:
        """Set the callback for a custom ID.

        Parameters
        ----------
        custom_id
            The custom ID to set the callback for.

            This will be matched against `interaction.custom_id.split(":", 1)[0]`,
            allowing metadata to be stored after a `":"`.
        callback
            The callback to set.

        Raises
        ------
        ValueError
            If `":"` is in the custom ID.
        """
        if ":" in custom_id:
            raise RuntimeError("Custom ID cannot contain `:`")

        self._id_to_callback[custom_id] = callback
        return self

    def with_callback(self, custom_id: str, /) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        """Set the callback for a custom ID through a decorator callback.

        Parameters
        ----------
        custom_id
            The custom ID to set the callback for.

            This will be matched against `interaction.custom_id.split(":", 1)[0]`,
            allowing metadata to be stored after a `":"`.

        Returns
        -------
        collections.abc.Callable[[CallbackSig], CallbackSig]
            Decorator callback used to set a custom ID's callback.

        Raises
        ------
        ValueError
            If `":"` is in the custom ID.
        """

        def decorator(callback: _CallbackSigT, /) -> _CallbackSigT:
            self.set_callback(custom_id, callback)
            return callback

        return decorator


class WaitForExecutor(AbstractComponentExecutor, timeouts.AbstractTimeout):
    """Component executor used to wait for a single component interaction.

    This should also be passed for `timeout=`.

    Examples
    --------
    ```py
    message = await ctx.respond("hi, pick an option", components=[...], ensure_result=True)

    executor = yuyo.components.WaitFor(authors=[ctx.author.id], timeout=datetime.timedelta(seconds=30))
    component_client.register_executor(executor, message=message, timeout=executor)

    try:
        result = await executor.wait_for()
    except asyncio.TimeoutError:
        await ctx.respond("timed out")
    else:
        await result.respond("...")
    ```
    """

    __slots__ = ("_authors", "_custom_ids", "_ephemeral_default", "_finished", "_future", "_timeout", "_timeout_at")

    def __init__(
        self,
        *,
        authors: typing.Optional[collections.Iterable[hikari.SnowflakeishOr[hikari.User]]] = None,
        custom_ids: collections.Collection[str] = (),
        ephemeral_default: bool = False,
        timeout: typing.Optional[datetime.timedelta],
    ) -> None:
        """Initialise a wait for executor.

        Parameters
        ----------
        authors
            Users who are allowed to use the components this represents.

            If no users are provided then the components will be public
            (meaning that anybody can use it).
        custom_ids
            Collection of the custom IDs this executor should be triggered by when
            registered globally.
        ephemeral_default
            Whether or not the responses made on contexts spawned from this paginator
            should default to ephemeral (meaning only the author can see them) unless
            `flags` is specified on the response method.
        timeout
            How long this should wait for a matching component interaction until it times-out.
        """
        self._authors = set(map(hikari.Snowflake, authors)) if authors else None
        self._custom_ids = custom_ids
        self._ephemeral_default = ephemeral_default
        self._finished = False
        self._future: typing.Optional[asyncio.Future[Context]] = None
        self._timeout = timeout
        self._timeout_at: typing.Optional[datetime.datetime] = None

    @property
    def custom_ids(self) -> collections.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._custom_ids

    @property
    def has_expired(self) -> bool:
        return bool(self._finished or self._timeout_at and _now() > self._timeout_at)

    def increment_uses(self) -> bool:
        return True

    async def wait_for(self) -> Context:
        """Wait for the next matching interaction.

        Returns
        -------
        Context
            The next matching interaction.

        Raises
        ------
        RuntimeError
            If the executor is already being waited for.
        asyncio.TimeoutError
            If the timeout is reached.
        """
        if self._future:
            raise RuntimeError("This executor is already being waited for")

        if self._timeout:
            self._timeout_at = _now() + self._timeout
            timeout = self._timeout.total_seconds()

        else:
            timeout = None

        self._future = asyncio.get_running_loop().create_future()
        try:
            return await asyncio.wait_for(self._future, timeout)

        finally:
            self._finished = True

    async def execute(self, ctx: Context, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        if self._finished:
            raise ExecutorClosed

        ctx.set_ephemeral_default(self._ephemeral_default)
        if not self._future:
            await ctx.create_initial_response("The bot isn't ready for that yet", ephemeral=True)
            return

        if self._authors and ctx.interaction.user.id not in self._authors:
            await ctx.create_initial_response("You are not allowed to use this component", ephemeral=True)
            return

        self._finished = True
        self._future.set_result(ctx)


WaitFor = WaitForExecutor
"""Alias of [WaitForExecutor][yuyo.components.WaitForExecutor]."""


class StreamExecutor(AbstractComponentExecutor, timeouts.AbstractTimeout):
    """Stream over the received component interactions.

    This should also be passed for `timeout=` and will reject contexts until it's opened.

    Examples
    --------
    ```py
    message = await ctx.respond("hi, pick an option", components=[...])
    stream = yuyo.components.Stream(authors=[ctx.author.id], timeout=datetime.timedelta(seconds=30))
    component_client.register_executor(stream, message=message, timeout=stream)

    with stream:
        async for result in stream:
            await result.respond("...")
    ```
    """

    __slots__ = ("_authors", "_custom_ids", "_ephemeral_default", "_finished", "_max_backlog", "_queue", "_timeout")

    def __init__(
        self,
        *,
        authors: typing.Optional[collections.Iterable[hikari.SnowflakeishOr[hikari.User]]],
        custom_ids: collections.Collection[str] = (),
        ephemeral_default: bool = False,
        max_backlog: int = 5,
        timeout: typing.Union[float, int, datetime.timedelta, None],
    ) -> None:
        """Initialise a stream executor.

        Parameters
        ----------
        authors
            Users who are allowed to use the components this represents.

            If [None][] is passed here then the paginator will be public (meaning that
            anybody can use it).
        custom_ids
            Collection of the custom IDs this executor should be triggered by when
            registered globally.
        ephemeral_default
            Whether or not the responses made on contexts spawned from this paginator
            should default to ephemeral (meaning only the author can see them) unless
            `flags` is specified on the response method.
        max_backlog
            The maximum amount of interaction contexts this should store in its backlog.

            Any extra interactions will be rejected while the backlog is full.
        timeout
            How long this should wait between iterations for a matching
            interaction to be recveived before ending the iteration.

            This alone does not close the stream.
        """
        if timeout is not None and isinstance(timeout, datetime.timedelta):
            timeout = timeout.total_seconds()

        self._authors = set(map(hikari.Snowflake, authors)) if authors else None
        self._custom_ids = custom_ids
        self._ephemeral_default = ephemeral_default
        self._finished = False
        self._max_backlog = max_backlog
        self._queue: typing.Optional[asyncio.Queue[ComponentContext]] = None
        self._timeout = timeout

    @property
    def custom_ids(self) -> collections.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._custom_ids

    @property
    def has_expired(self) -> bool:
        return self._finished

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[type[BaseException]],
        exc: typing.Optional[BaseException],
        exc_traceback: typing.Optional[types.TracebackType],
    ) -> Self:
        self.close()
        return self

    def increment_uses(self) -> bool:
        return self._finished

    def open(self) -> None:
        if self._queue is not None:
            raise RuntimeError("Stream is already active")

        # Assert that this is called in a running event loop
        asyncio.get_running_loop()
        self._finished = False
        self._queue = asyncio.Queue(maxsize=self._max_backlog)

    def close(self) -> None:
        if self._queue is None:
            raise RuntimeError("Stream is not active")

        self._finished = True
        self._queue = None

    def __aiter__(self) -> collections.AsyncIterator[ComponentContext]:
        return self

    async def __anext__(self) -> ComponentContext:
        if self._queue is None:
            raise RuntimeError("Stream is not active")

        try:
            return await asyncio.wait_for(self._queue.get(), timeout=self._timeout)

        except asyncio.TimeoutError:
            raise StopAsyncIteration from None

    async def execute(self, ctx: ComponentContext, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        ctx.set_ephemeral_default(self._ephemeral_default)
        if self._finished:
            raise ExecutorClosed

        if not self._queue:
            await ctx.create_initial_response("This bot isn't ready for that yet", ephemeral=True)
            return

        if self._authors and ctx.interaction.user.id not in self._authors:
            await ctx.create_initial_response("You are not allowed to use this component", ephemeral=True)
            return

        try:
            self._queue.put_nowait(ctx)
        except asyncio.QueueFull:
            await ctx.create_initial_response("This bot isn't ready for that yet", ephemeral=True)


Stream = StreamExecutor
"""Alias of [StreamExecutor][yuyo.components.StreamExecutor]."""


class _TextSelectMenuBuilder(hikari.impl.TextSelectMenuBuilder[_T]):
    __slots__ = ()

    def build(self) -> collections.MutableMapping[str, typing.Any]:
        payload = super().build()
        max_values = min(len(self.options), self.max_values)
        payload["max_values"] = max_values
        return payload


_CHANNEL_TYPES: dict[type[hikari.PartialChannel], set[hikari.ChannelType]] = {
    hikari.GuildTextChannel: {hikari.ChannelType.GUILD_TEXT},
    hikari.DMChannel: {hikari.ChannelType.DM},
    hikari.GuildVoiceChannel: {hikari.ChannelType.GUILD_VOICE},
    hikari.GroupDMChannel: {hikari.ChannelType.GROUP_DM},
    hikari.GuildCategory: {hikari.ChannelType.GUILD_CATEGORY},
    hikari.GuildNewsChannel: {hikari.ChannelType.GUILD_NEWS},
    hikari.GuildStageChannel: {hikari.ChannelType.GUILD_STAGE},
    hikari.GuildNewsThread: {hikari.ChannelType.GUILD_NEWS_THREAD},
    hikari.GuildPublicThread: {hikari.ChannelType.GUILD_PUBLIC_THREAD},
    hikari.GuildPrivateThread: {hikari.ChannelType.GUILD_PRIVATE_THREAD},
    hikari.GuildForumChannel: {hikari.ChannelType.GUILD_FORUM},
}
"""Mapping of hikari channel classes to the raw channel types which are compatible for it."""


for _channel_cls, _types in _CHANNEL_TYPES.copy().items():
    for _mro_type in _channel_cls.mro():
        if isinstance(_mro_type, type) and issubclass(  # pyright: ignore[reportUnnecessaryIsInstance]
            _mro_type, hikari.PartialChannel
        ):
            try:
                _CHANNEL_TYPES[_mro_type].update(_types)
            except KeyError:
                _CHANNEL_TYPES[_mro_type] = _types.copy()

# This isn't a base class but it should still act like an indicator for any channel type.
_CHANNEL_TYPES[hikari.InteractionChannel] = _CHANNEL_TYPES[hikari.PartialChannel]


def _parse_channel_types(*channel_types: typing.Union[type[hikari.PartialChannel], int]) -> list[hikari.ChannelType]:
    """Parse a channel types collection to a list of channel type integers."""
    types_iter = itertools.chain.from_iterable(
        (hikari.ChannelType(type_),) if isinstance(type_, int) else _CHANNEL_TYPES[type_] for type_ in channel_types
    )

    try:
        return list(dict.fromkeys(types_iter))

    except KeyError as exc:
        raise ValueError(f"Unknown channel type {exc.args[0]}") from exc


class _ComponentDescriptor(abc.ABC):
    """Abstract class used to mark components on an action column class."""

    __slots__ = ()

    @abc.abstractmethod
    def to_field(self, cls_path: str, name: str, /) -> _StaticField:
        """Convert this descriptor to a static field."""


class _CallableComponentDescriptor(_ComponentDescriptor, typing.Generic[_SelfT, _P]):
    """Base class used to represent components by decorating a callback."""

    __slots__ = ("_callback", "_custom_id")

    def __init__(
        self,
        callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT],
        custom_id: typing.Optional[str],
        /,
    ) -> None:
        if custom_id is None:
            self._custom_id: typing.Optional[_internal.MatchId] = None

        else:
            self._custom_id = _internal.gen_custom_id(custom_id)

        self._callback = callback

    async def __call__(self, self_: _SelfT, /, *args: _P.args, **kwargs: _P.kwargs) -> None:
        return await self._callback(self_, *args, **kwargs)

    @typing.overload
    def __get__(
        self, obj: None, obj_type: typing.Optional[type[typing.Any]] = None
    ) -> collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]: ...

    @typing.overload
    def __get__(
        self, obj: object, obj_type: typing.Optional[type[typing.Any]] = None
    ) -> collections.Callable[_P, _CoroT]: ...

    def __get__(
        self, obj: typing.Optional[object], obj_type: typing.Optional[type[typing.Any]] = None
    ) -> collections.Callable[..., typing.Any]:
        if obj is None:
            return self._callback

        return types.MethodType(self._callback, obj)

    def _get_custom_id(self, cls_path: str, name: str, /) -> _internal.MatchId:
        if self._custom_id is not None:
            return self._custom_id

        # callback.__module__ and .__qualname__ will show the module and
        # class a callback was inherited from rather than the class it was
        # accessed on.
        path = f"{cls_path}.{name}".encode()
        custom_id = base64.b85encode(hashlib.blake2b(path, digest_size=8).digest()).decode()
        assert ":" not in custom_id
        return _internal.MatchId(custom_id, custom_id)


class _StaticButton(_CallableComponentDescriptor[_SelfT, _P]):
    """Used to represent a button method."""

    __slots__ = ("_style", "_emoji", "_label", "_is_disabled")

    def __init__(
        self,
        style: hikari.InteractiveButtonTypesT,
        callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT],
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> None:
        super().__init__(callback, custom_id)
        self._style: hikari.InteractiveButtonTypesT = style
        self._emoji = emoji
        self._label = label
        self._is_disabled = is_disabled

    def to_field(self, cls_path: str, name: str, /) -> _StaticField:
        id_match, custom_id = self._get_custom_id(cls_path, name)
        return _StaticField(
            id_match,
            self._callback,
            hikari.impl.InteractiveButtonBuilder(
                style=self._style,
                custom_id=custom_id,
                emoji=self._emoji,
                label=self._label,
                is_disabled=self._is_disabled,
            ),
            name=name,
            self_bound=True,
        )


def as_interactive_button(
    style: hikari.InteractiveButtonTypesT,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
    label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    is_disabled: bool = False,
) -> collections.Callable[
    [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _StaticButton[_SelfT, _P]
]:
    """Declare an interactive button on an action column class.

    Either `emoji` xor `label` must be provided to be the button's
    displayed label.

    Parameters
    ----------
    style
        The button's style.
    custom_id
        The button's custom ID.

        Defaults to a constant ID that's generated from the path to the
        decorated callback (which includes the class and module qualnames).

        Only `custom_id.split(":", 1)[0]` will be used to match against
        interactions. Anything after `":"` is metadata and the custom ID
        cannot be longer than 100 characters in total.
    emoji
        The button's emoji.
    label
        The button's label.
    is_disabled
        Whether the button should be marked as disabled.

    Examples
    --------
    ```py
    class CustomColumn(components.ActionColumnExecutor):
        @components.as_interactive_button(ButtonStyle.DANGER, label="label")
        async def on_button(self, ctx: components.Context) -> None:
            ...
    ```
    """
    return lambda callback: _StaticButton(style, callback, custom_id, emoji, label, is_disabled)


class _StaticLinkButton(_ComponentDescriptor):
    __slots__ = ("_custom_id", "_url", "_emoji", "_label", "_is_disabled")

    def __init__(
        self,
        url: str,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> None:
        # While Link buttons don't actually have custom IDs, this is currently
        # necessary to avoid duplication.
        self._custom_id = _internal.random_custom_id()
        self._url = url
        self._emoji = emoji
        self._label = label
        self._is_disabled = is_disabled

    def to_field(self, _: str, __: str, /) -> _StaticField:
        return _StaticField(
            self._custom_id,
            None,
            hikari.impl.LinkButtonBuilder(
                url=self._url, emoji=self._emoji, label=self._label, is_disabled=self._is_disabled
            ),
        )


def link_button(
    url: str,
    /,
    *,
    emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
    label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    is_disabled: bool = False,
) -> _StaticLinkButton:
    """Declare an link button on an action column class.

    Either `emoji` xor `label` must be provided to be the button's
    displayed label.

    Parameters
    ----------
    url
        The button's url.
    emoji
        The button's emoji.
    label
        The button's label.
    is_disabled
        Whether the button should be marked as disabled.

    Examples
    --------
    ```py
    class CustomColumn(components.ActionColumnExecutor):
        link_button = components.link_button("https://example.com", label="label")
    ```
    """
    return _StaticLinkButton(url, emoji, label, is_disabled)


class _SelectMenu(_CallableComponentDescriptor[_SelfT, _P]):
    __slots__ = ("_type", "_placeholder", "_min_values", "_max_values", "_is_disabled")

    def __init__(
        self,
        callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT],
        type_: typing.Union[hikari.ComponentType, int],
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> None:
        super().__init__(callback, custom_id)
        self._type = hikari.ComponentType(type_)
        self._placeholder = placeholder
        self._min_values = min_values
        self._max_values = max_values
        self._is_disabled = is_disabled

    def to_field(self, cls_path: str, name: str, /) -> _StaticField:
        id_match, custom_id = self._get_custom_id(cls_path, name)
        return _StaticField(
            id_match,
            self._callback,
            hikari.impl.SelectMenuBuilder(
                type=self._type,
                custom_id=custom_id,
                placeholder=self._placeholder,
                min_values=self._min_values,
                max_values=self._max_values,
                is_disabled=self._is_disabled,
            ),
            name=name,
            self_bound=True,
        )


def as_select_menu(
    type_: typing.Union[hikari.ComponentType, int],
    /,
    *,
    custom_id: typing.Optional[str] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> collections.Callable[
    [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _SelectMenu[_SelfT, _P]
]:
    """Declare a select menu on an action column class.

    The following decorators should be used instead:

    * [as_channel_menu][yuyo.components.as_channel_menu]
    * [as_mentionable_menu][yuyo.components.as_mentionable_menu]
    * [as_role_menu][yuyo.components.as_role_menu]
    * [as_text_menu][yuyo.components.as_text_menu]
    * [as_user_menu][yuyo.components.as_user_menu]
    """
    return lambda callback: _SelectMenu(callback, type_, custom_id, placeholder, min_values, max_values, is_disabled)


@typing.overload
def as_mentionable_menu(
    callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT], /
) -> _SelectMenu[_SelfT, _P]: ...


@typing.overload
def as_mentionable_menu(
    *,
    custom_id: typing.Optional[str] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> collections.Callable[
    [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _SelectMenu[_SelfT, _P]
]: ...


def as_mentionable_menu(
    callback: typing.Optional[collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]] = None,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> typing.Union[
    collections.Callable[
        [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _SelectMenu[_SelfT, _P]
    ],
    _SelectMenu[_SelfT, _P],
]:
    """Declare a mentionable select menu on an action column class.

    Parameters
    ----------
    custom_id
        The select menu's custom ID.

        Defaults to a constant ID that's generated from the path to the
        decorated callback (which includes the class and module qualnames).

        Only `custom_id.split(":", 1)[0]` will be used to match against
        interactions. Anything after `":"` is metadata and the custom ID
        cannot be longer than 100 characters in total.
    placeholder
        Placeholder text to show when no entries have been selected.
    min_values
        The minimum amount of entries which need to be selected.
    max_values
        The maximum amount of entries which can be selected.
    is_disabled
        Whether this select menu should be marked as disabled.

    Examples
    --------
    ```py
    class CustomColumn(components.ActionColumnExecutor):
        @components.as_mentionable_menu(max_values=5)
        async def on_select_menu(self, ctx: components.Context) -> None:
            ...
    ```
    """
    return _consume(
        callback,
        lambda callback_: _SelectMenu(
            callback_,
            hikari.ComponentType.MENTIONABLE_SELECT_MENU,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        ),
    )


@typing.overload
def as_role_menu(
    callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT], /
) -> _SelectMenu[_SelfT, _P]: ...


@typing.overload
def as_role_menu(
    *,
    custom_id: typing.Optional[str] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> collections.Callable[
    [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _SelectMenu[_SelfT, _P]
]: ...


def as_role_menu(
    callback: typing.Optional[collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]] = None,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> typing.Union[
    collections.Callable[
        [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _SelectMenu[_SelfT, _P]
    ],
    _SelectMenu[_SelfT, _P],
]:
    """Declare a role select menu on an action column class.

    Parameters
    ----------
    custom_id
        The select menu's custom ID.

        Defaults to a constant ID that's generated from the path to the
        decorated callback (which includes the class and module qualnames).

        Only `custom_id.split(":", 1)[0]` will be used to match against
        interactions. Anything after `":"` is metadata and the custom ID
        cannot be longer than 100 characters in total.
    placeholder
        Placeholder text to show when no entries have been selected.
    min_values
        The minimum amount of entries which need to be selected.
    max_values
        The maximum amount of entries which can be selected.
    is_disabled
        Whether this select menu should be marked as disabled.

    Examples
    --------
    ```py
    class CustomColumn(components.ActionColumnExecutor):
        @components.as_role_menu(max_values=5)
        async def on_select_menu(self, ctx: components.Context) -> None:
            ...
    ```
    """
    return _consume(
        callback,
        lambda callback_: _SelectMenu(
            callback_,
            hikari.ComponentType.ROLE_SELECT_MENU,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        ),
    )


@typing.overload
def as_user_menu(
    callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT], /
) -> _SelectMenu[_SelfT, _P]: ...


@typing.overload
def as_user_menu(
    *,
    custom_id: typing.Optional[str] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> collections.Callable[
    [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _SelectMenu[_SelfT, _P]
]: ...


def as_user_menu(
    callback: typing.Optional[collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]] = None,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> typing.Union[
    collections.Callable[
        [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _SelectMenu[_SelfT, _P]
    ],
    _SelectMenu[_SelfT, _P],
]:
    """Declare a user select menu on an action column class.

    Parameters
    ----------
    custom_id
        The select menu's custom ID.

        Defaults to a constant ID that's generated from the path to the
        decorated callback (which includes the class and module qualnames).

        Only `custom_id.split(":", 1)[0]` will be used to match against
        interactions. Anything after `":"` is metadata and the custom ID
        cannot be longer than 100 characters in total.
    placeholder
        Placeholder text to show when no entries have been selected.
    min_values
        The minimum amount of entries which need to be selected.
    max_values
        The maximum amount of entries which can be selected.
    is_disabled
        Whether this select menu should be marked as disabled.

    Examples
    --------
    ```py
    class CustomColumn(components.ActionColumnExecutor):
        @components.as_user_menu(max_values=5)
        async def on_select_menu(self, ctx: components.Context) -> None:
            ...
    ```
    """
    return _consume(
        callback,
        lambda callback_: _SelectMenu(
            callback_,
            hikari.ComponentType.USER_SELECT_MENU,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        ),
    )


class _ChannelSelect(_CallableComponentDescriptor[_SelfT, _P]):
    __slots__ = ("_channel_types", "_placeholder", "_min_values", "_max_values", "_is_disabled")

    def __init__(
        self,
        callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT],
        custom_id: typing.Optional[str] = None,
        channel_types: typing.Optional[
            collections.Sequence[typing.Union[hikari.ChannelType, type[hikari.PartialChannel]]]
        ] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> None:
        super().__init__(callback, custom_id)
        self._channel_types = _parse_channel_types(*channel_types) if channel_types else []
        self._placeholder = placeholder
        self._min_values = min_values
        self._max_values = max_values
        self._is_disabled = is_disabled

    def to_field(self, cls_path: str, name: str, /) -> _StaticField:
        id_match, custom_id = self._get_custom_id(cls_path, name)
        return _StaticField(
            id_match,
            self._callback,
            hikari.impl.ChannelSelectMenuBuilder(
                custom_id=custom_id,
                placeholder=self._placeholder,
                min_values=self._min_values,
                max_values=self._max_values,
                is_disabled=self._is_disabled,
                channel_types=self._channel_types,
            ),
            name=name,
            self_bound=True,
        )


@typing.overload
def as_channel_menu(
    callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT], /
) -> _ChannelSelect[_SelfT, _P]: ...


@typing.overload
def as_channel_menu(
    *,
    custom_id: typing.Optional[str] = None,
    channel_types: typing.Optional[
        collections.Sequence[typing.Union[hikari.ChannelType, type[hikari.PartialChannel]]]
    ] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> collections.Callable[
    [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _ChannelSelect[_SelfT, _P]
]: ...


def as_channel_menu(
    callback: typing.Optional[collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]] = None,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    channel_types: typing.Optional[
        collections.Sequence[typing.Union[hikari.ChannelType, type[hikari.PartialChannel]]]
    ] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> typing.Union[
    collections.Callable[
        [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _ChannelSelect[_SelfT, _P]
    ],
    _ChannelSelect[_SelfT, _P],
]:
    """Declare a channel select menu on an action column class.

    Parameters
    ----------
    channel_types
        Sequence of the types of channels this select menu should show as options.
    custom_id
        The select menu's custom ID.

        Defaults to a constant ID that's generated from the path to the
        decorated callback (which includes the class and module qualnames).

        Only `custom_id.split(":", 1)[0]` will be used to match against
        interactions. Anything after `":"` is metadata and the custom ID
        cannot be longer than 100 characters in total.
    placeholder
        Placeholder text to show when no entries have been selected.
    min_values
        The minimum amount of entries which need to be selected.
    max_values
        The maximum amount of entries which can be selected.
    is_disabled
        Whether this select menu should be marked as disabled.

    Examples
    --------
    ```py
    class CustomColumn(components.ActionColumnExecutor):
        @components.as_channel_menu(channel_types=[hikari.TextableChannel])
        async def on_channel_menu(self, ctx: components.Context) -> None:
            ...
    ```
    """
    return _consume(
        callback,
        lambda callback_: _ChannelSelect(
            callback_, custom_id, channel_types, placeholder, min_values, max_values, is_disabled
        ),
    )


class _TextMenuDescriptor(_CallableComponentDescriptor[_SelfT, _P]):
    __slots__ = ("_options", "_placeholder", "_min_values", "_max_values", "_is_disabled")

    def __init__(
        self,
        callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT],
        custom_id: typing.Optional[str] = None,
        options: collections.Sequence[hikari.api.SelectOptionBuilder] = (),
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> None:
        super().__init__(callback, custom_id)
        self._options = list(options)
        self._placeholder = placeholder
        self._min_values = min_values
        self._max_values = max_values
        self._is_disabled = is_disabled

    def to_field(self, cls_path: str, name: str, /) -> _StaticField:
        id_match, custom_id = self._get_custom_id(cls_path, name)
        return _StaticField(
            id_match,
            self._callback,
            _TextSelectMenuBuilder(
                parent=self,
                custom_id=custom_id,
                placeholder=self._placeholder,
                options=self._options.copy(),
                min_values=self._min_values,
                max_values=self._max_values,
                is_disabled=self._is_disabled,
            ),
            name=name,
            self_bound=True,
        )

    def add_option(
        self,
        label: str,
        value: str,
        /,
        *,
        description: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        is_default: bool = False,
    ) -> Self:
        self._options.append(
            hikari.impl.SelectOptionBuilder(
                label=label, value=value, description=description, is_default=is_default, emoji=emoji
            )
        )
        return self


@typing.overload
def as_text_menu(
    callback: collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT], /
) -> _TextMenuDescriptor[_SelfT, _P]: ...


@typing.overload
def as_text_menu(
    *,
    custom_id: typing.Optional[str] = None,
    options: collections.Sequence[hikari.api.SelectOptionBuilder] = (),
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> collections.Callable[
    [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _TextMenuDescriptor[_SelfT, _P]
]: ...


def as_text_menu(
    callback: typing.Optional[collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]] = None,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    options: collections.Sequence[hikari.api.SelectOptionBuilder] = (),
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> typing.Union[
    collections.Callable[
        [collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]], _TextMenuDescriptor[_SelfT, _P]
    ],
    _TextMenuDescriptor[_SelfT, _P],
]:
    """Declare a text select menu on an action column class.

    Parameters
    ----------
    custom_id
        The select menu's custom ID.

        Defaults to a constant ID that's generated from the path to the
        decorated callback (which includes the class and module qualnames).

        Only `custom_id.split(":", 1)[0]` will be used to match against
        interactions. Anything after `":"` is metadata and the custom ID
        cannot be longer than 100 characters in total.
    options
        The text select's options.

        These can also be added by using [components.with_option][yuyo.components.with_option].
    placeholder
        Placeholder text to show when no entries have been selected.
    min_values
        The minimum amount of entries which need to be selected.
    max_values
        The maximum amount of entries which can be selected.
    is_disabled
        Whether this select menu should be marked as disabled.

    Examples
    --------
    ```py
    class CustomColumn(components.ActionColumnExecutor):
        @components.with_option("label", "value")
        @components.as_text_menu
        async def on_text_menu(self, ctx: components.Context) -> None:
            ...
    ```
    """
    return _consume(
        callback,
        lambda callback_: _TextMenuDescriptor(
            callback_, custom_id, options, placeholder, min_values, max_values, is_disabled
        ),
    )


def with_option(
    label: str,
    value: str,
    /,
    *,
    description: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
    is_default: bool = False,
) -> collections.Callable[[_TextMenuT], _TextMenuT]:
    """Add an option to a text select menu through a decorator call.

    Parameters
    ----------
    label
        The option's label.
    value
        The option's value.
    description
        The option's description.
    emoji
        Emoji to display for the option.
    is_default
        Whether the option should be marked as selected by default.

    Examples
    --------
    ```py
    class Column(components.AbstractColumnExecutor):
        @components.with_option("other label", "other value")
        @components.with_option("label", "value")
        @components.as_text_menu
        async def on_text_menu(self, ctx: components.Context) -> None:
            ...
    ```

    ```py
    column = components.ActionColumnExecutor()

    @components.with_option("name3", "value3")
    @components.with_option("name2", "value2")
    @components.with_option("name1", "value1")
    @column.with_text_menu
    async def on_text_menu(ctx: components.Context) -> None:
        ...
    ```
    """
    return lambda text_select: text_select.add_option(
        label, value, description=description, emoji=emoji, is_default=is_default
    )


class _BuilderDescriptor(_ComponentDescriptor):
    __slots__ = ("_builder", "_custom_id")

    def __init__(self, builder: hikari.api.ComponentBuilder, /) -> None:
        self._builder = builder
        # While these builders don't necessarily have custom IDs, one is
        # currently generated to avoid duplication.
        self._custom_id = _internal.random_custom_id()

    def to_field(self, cls_path: str, name: str) -> _StaticField:
        return _StaticField(self._custom_id, None, self._builder)


def builder(builder: hikari.api.ComponentBuilder, /) -> _BuilderDescriptor:
    """Add a raw component builder to a column through a descriptor.

    This is mostly for adding components where the custom ID is already
    registered as a separate constant executor.

    Parameters
    ----------
    builder
        The component builder to add to the column.

    Examples
    --------
    ```py
    class CustomColumn(components.ActionColumnExecutor):
        link_button = components.builder(hikari.impl.InteractiveButtonBuilder(
            style=hikari.ButtonStyle.PRIMARY, custom_id="CUSTOM_ID", label="yeet"
        ))
    ```
    """
    return _BuilderDescriptor(builder)


class _StaticField:
    __slots__ = ("builder", "callback", "id_match", "is_self_bound", "name")

    def __init__(
        self,
        id_match: str,
        callback: typing.Optional[CallbackSig],
        builder: hikari.api.ComponentBuilder,
        /,
        *,
        name: str = "",
        self_bound: bool = False,
    ) -> None:
        self.builder: hikari.api.ComponentBuilder = builder
        self.callback: typing.Optional[CallbackSig] = callback
        self.id_match: str = id_match
        self.is_self_bound: bool = self_bound
        self.name: str = name


@typing.runtime_checkable
class _CustomIdProto(typing.Protocol):
    def set_custom_id(self, value: str, /) -> object:
        raise NotImplementedError

    @classmethod
    def __subclasshook__(cls, value: typing.Any) -> bool:
        try:
            value.set_custom_id

        except AttributeError:
            return False

        return True


class ActionColumnExecutor(AbstractComponentExecutor):
    """Executor which handles columns of action rows.

    This can be used to declare and handle the components on a message a couple
    of ways.

    To send a column's components pass
    [ActionColumnExecutor.rows][yuyo.components.ActionColumnExecutor.rows] as `components`
    when calling the create message method (e.g. `respond`/`create_message`).

    Examples
    --------
    Sub-components can be added to an instance of the column executor using
    chainable methods on it:

    ```py
    async def callback_1(ctx: components.Context) -> None:
        await ctx.respond("meow")

    components = (
        components.ActionColumnExecutor()
        .add_interactive_button(hikari.ButtonStyle.PRIMARY, chainable, label="Button 1")
        .add_link_button("https://example.com", label="Button 2",)
    )
    ```

    Alternatively, subclasses of [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
    can act as a template where "static" fields are included on all instances
    and subclasses of that class:

    !!! note
        Since decorators are executed from the bottom upwards fields added
        through decorator calls will follow the same order.

    ```py
    async def callback_1(ctx: components.Context) -> None:
        await ctx.respond("meow")

    async def callback_2(ctx: components.Context) -> None:
        await ctx.respond("meow")

    @components.with_static_select_menu(callback_1, hikari.ComponentType.USER_SELECT_MENU, max_values=5)
    class CustomColumn(components.ActionColumnExecutor):
        __slots__ = ("special_string",)  # ActionColumnExecutor supports slotting.

        # The init can be overridden to store extra data on the column object when subclassing.
        def __init__(self, special_string: str, timeout: typing.Optional[datetime.timedelta] = None):
            super().__init__(timeout=timeout)
            self.special_string = special_string

    (
        CustomColumn.add_static_text_menu(callback_2, min_values=0, max_values=3)
        # The following calls are all adding options to the added
        # text select menu.
        .add_option("Option 1", "value 1")
        .add_option("Option 2", "value 2")
        .add_option("Option 3", "value 3")
    )
    ```

    There's also class descriptors which can be used to declare static
    components. The following descriptors work by decorating their
    component's callback:

    * [as_interactive_button][yuyo.components.as_interactive_button]
    * [as_channel_menu][yuyo.components.as_channel_menu]
    * [as_mentionable_menu][yuyo.components.as_mentionable_menu]
    * [as_role_menu][yuyo.components.as_role_menu]
    * [as_text_menu][yuyo.components.as_text_menu]
    * [as_user_menu][yuyo.components.as_user_menu]

    [link_button][yuyo.components.link_button] returns a descriptor without
    decorating any callback.

    ```py
    class CustomColumn(components.ActionColumnExecutor):
        @components.as_interactive_button(ButtonStyle.PRIMARY, label="label")
        async def left_button(self, ctx: components.Context) -> None:
            ...

        link_button = components.link_button(url="https://example.com", label="Go to page")

        @components.as_interactive_button(ButtonStyle.SECONDARY, label="meow")
        async def right_button(self, ctx: components.Context) -> None:
            ...

        @components.as_channel_menu(channel_types=[hikari.TextableChannel], custom_id="eep")
        async def text_select_menu(self, ctx: components.Context) -> None:
            ...
    ```
    """

    __slots__ = ("_authors", "_callbacks", "_ephemeral_default", "_rows")

    _added_static_fields: typing.ClassVar[dict[str, _StaticField]] = {}
    """Dict of match IDs to the static fields added to this class through add method calls.

    This doesn't include inherited fields.
    """

    _static_fields: typing.ClassVar[dict[str, _StaticField]] = {}
    """Dict of match IDs to the static fields on this class.

    This includes inherited fields and fields added through method calls.
    """

    def __init__(
        self,
        *,
        authors: typing.Optional[collections.Iterable[hikari.SnowflakeishOr[hikari.User]]] = None,
        ephemeral_default: bool = False,
        id_metadata: typing.Optional[collections.Mapping[str, str]] = None,
    ) -> None:
        """Initialise an action column executor.

        Parameters
        ----------
        authors
            Users who are allowed to use the components this represents.

            If no users are provided then the components will be public
            (meaning that anybody can use it).
        ephemeral_default
            Whether or not the responses made on contexts spawned from this executor
            should default to ephemeral (meaning only the author can see them) unless
            `flags` is specified on the response method.
        id_metadata
            Mapping of metadata to append to the custom IDs in this column.

            The keys in this can either be the match part of component custom
            IDs or the names of the component's callback when it was added
            using one of the `as_` class descriptors.
        """
        self._authors = set(map(hikari.Snowflake, authors)) if authors else None
        self._callbacks: dict[str, CallbackSig] = {}
        self._ephemeral_default = ephemeral_default
        self._rows: list[hikari.api.MessageActionRowBuilder] = []

        for field in self._static_fields.values():
            if id_metadata and (metadata := (id_metadata.get(field.id_match) or id_metadata.get(field.name))):
                builder = copy.copy(field.builder)
                assert isinstance(builder, _CustomIdProto)
                builder.set_custom_id(f"{field.id_match}:{metadata}")

            else:
                builder = field.builder

            _append_row(self._rows, is_button=field.builder.type is hikari.ComponentType.BUTTON).add_component(builder)

            if field.callback:
                self._callbacks[field.id_match] = (
                    types.MethodType(field.callback, self) if field.is_self_bound else field.callback
                )

    def __init_subclass__(cls, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init_subclass__(*args, **kwargs)
        cls._added_static_fields = {}
        cls._static_fields = {}
        added_static_fields: dict[str, _StaticField] = {}
        namespace: dict[str, typing.Any] = {}

        # This slice ignores [object, ...] and flips the order.
        for super_cls in cls.mro()[-2::-1]:
            if issubclass(super_cls, ActionColumnExecutor):
                added_static_fields.update(super_cls._added_static_fields)
                namespace.update(super_cls.__dict__)

        for name, attr in namespace.items():
            cls_path = f"{cls.__module__}.{cls.__qualname__}"
            if isinstance(attr, _ComponentDescriptor):
                field = attr.to_field(cls_path, name)
                cls._static_fields[field.id_match] = field

        cls._static_fields.update(added_static_fields)

    @property
    def custom_ids(self) -> collections.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._callbacks

    @property
    def rows(self) -> collections.Sequence[hikari.api.MessageActionRowBuilder]:
        """The rows in this column."""
        return self._rows.copy()

    async def execute(self, ctx: Context, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        ctx.set_ephemeral_default(self._ephemeral_default)

        if self._authors and ctx.interaction.user.id not in self._authors:
            await ctx.create_initial_response("You are not allowed to use this component", ephemeral=True)
            return

        callback = self._callbacks[ctx.id_match]
        await ctx.client.alluka.call_with_async_di(callback, ctx)

    def add_builder(self, builder: hikari.api.ComponentBuilder, /) -> Self:
        """Add a raw component builder to this action column.

        This is mostly for adding components where the custom ID is already
        registered as a separate constant executor.

        Parameters
        ----------
        builder
            The component builder to add to the column.
        """
        _append_row(self._rows, is_button=builder.type is hikari.ComponentType.BUTTON).add_component(builder)
        return self

    @classmethod
    def add_static_builder(cls, builder: hikari.api.ComponentBuilder, /) -> type[Self]:
        """Add a raw component builder to all subclasses and instances of this column.

        This is mostly for adding components where the custom ID is already
        registered as a separate constant executor.

        Parameters
        ----------
        builder
            The component builder to add to the column class.
        """
        # While these builders don't necessarily have custom IDs, one is
        # currently generated to avoid duplication.
        custom_id = _internal.random_custom_id()
        field = _StaticField(custom_id, None, builder)
        cls._added_static_fields[custom_id] = field
        cls._static_fields[custom_id] = field
        return cls

    def add_interactive_button(
        self,
        style: hikari.InteractiveButtonTypesT,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        """Add an interactive button to this action column.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        callback
            The button's execution callback.
        custom_id
            The button's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        emoji
            The button's emoji.
        label
            The button's label.
        is_disabled
            Whether the button should be marked as disabled.

        Returns
        -------
        Self
            The action column to enable chained calls.
        """
        id_match, custom_id = _internal.gen_custom_id(custom_id)
        _append_row(self._rows, is_button=True).add_interactive_button(
            style, custom_id, emoji=emoji, label=label, is_disabled=is_disabled
        )
        self._callbacks[id_match] = callback
        return self

    def with_interactive_button(
        self,
        style: hikari.InteractiveButtonTypesT,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        """Add an interactive button to this action column through a decorator call.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        custom_id
            The button's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        emoji
            The button's emoji.
        label
            The button's label.
        is_disabled
            Whether the button should be marked as disabled.
        """

        def decorator(callback: _CallbackSigT, /) -> _CallbackSigT:
            self.add_interactive_button(
                style, callback, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
            )
            return callback

        return decorator

    @classmethod
    def add_static_interactive_button(
        cls,
        style: hikari.InteractiveButtonTypesT,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> type[Self]:
        """Add an interactive button to all subclasses and instances of this action column class.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        callback
            The button's execution callback.
        custom_id
            The button's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        emoji
            The button's emoji.
        label
            The button's label.
        is_disabled
            Whether the button should be marked as disabled.

        Returns
        -------
        type[Self]
            The action column class to enable chained calls.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        if cls is ActionColumnExecutor:
            raise RuntimeError("Can only add static components to subclasses")

        id_match, custom_id = _internal.gen_custom_id(custom_id)
        field = _StaticField(
            id_match,
            callback,
            hikari.impl.InteractiveButtonBuilder(
                style=style, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
            ),
        )
        cls._added_static_fields[custom_id] = field
        cls._static_fields[custom_id] = field
        return cls

    @classmethod
    def with_static_interactive_button(
        cls,
        style: hikari.InteractiveButtonTypesT,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        """Add a static interactive button to this action column class through a decorator call.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        custom_id
            The button's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        emoji
            The button's emoji.
        label
            The button's label.
        is_disabled
            Whether the button should be marked as disabled.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """

        def decorator(callback: _CallbackSigT, /) -> _CallbackSigT:
            cls.add_static_interactive_button(
                style, callback, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
            )
            return callback

        return decorator

    def add_link_button(
        self,
        url: str,
        /,
        *,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        """Add a link button to this action column.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        url
            The button's url.
        emoji
            The button's emoji.
        label
            The button's label.
        is_disabled
            Whether the button should be marked as disabled.

        Returns
        -------
        Self
            The action column to enable chained calls.
        """
        _append_row(self._rows, is_button=True).add_link_button(url, emoji=emoji, label=label, is_disabled=is_disabled)
        return self

    @classmethod
    def add_static_link_button(
        cls,
        url: str,
        /,
        *,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> type[Self]:
        """Add a link button to all subclasses and instances of this action column class.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        url
            The button's url.
        emoji
            The button's emoji.
        label
            The button's label.
        is_disabled
            Whether the button should be marked as disabled.

        Returns
        -------
        type[Self]
            The action column class to enable chained calls.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        if cls is ActionColumnExecutor:
            raise RuntimeError("Can only add static components to subclasses")

        custom_id = _internal.random_custom_id()
        field = _StaticField(
            custom_id, None, hikari.impl.LinkButtonBuilder(url=url, emoji=emoji, label=label, is_disabled=is_disabled)
        )
        cls._added_static_fields[custom_id] = field
        cls._static_fields[custom_id] = field
        return cls

    def add_select_menu(
        self,
        type_: typing.Union[hikari.ComponentType, int],
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> Self:
        """Add a select menu to this action column.

        The following methods should be used instead:

        * [.add_channel_menu][yuyo.components.ActionColumnExecutor.add_channel_menu]
        * [.add_mentionable_menu][yuyo.components.ActionColumnExecutor.add_mentionable_menu]
        * [.add_role_menu][yuyo.components.ActionColumnExecutor.add_role_menu]
        * [.add_text_menu][yuyo.components.ActionColumnExecutor.add_text_menu]
        * [.add_user_menu][yuyo.components.ActionColumnExecutor.add_user_menu]
        """
        id_match, custom_id = _internal.gen_custom_id(custom_id)
        _append_row(self._rows).add_select_menu(
            type_,
            custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )
        self._callbacks[id_match] = callback
        return self

    @classmethod
    def add_static_select_menu(
        cls,
        type_: typing.Union[hikari.ComponentType, int],
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> type[Self]:
        """Add a select menu to all subclasses and instances of this action column class.

        The following class methods should be used instead:

        * [.add_static_channel_menu][yuyo.components.ActionColumnExecutor.add_static_channel_menu]
        * [.add_static_mentionable_menu][yuyo.components.ActionColumnExecutor.add_static_mentionable_menu]
        * [.add_static_role_menu][yuyo.components.ActionColumnExecutor.add_static_role_menu]
        * [.add_static_text_menu][yuyo.components.ActionColumnExecutor.add_static_text_menu]
        * [.add_static_user_menu][yuyo.components.ActionColumnExecutor.add_static_user_menu]
        """
        if cls is ActionColumnExecutor:
            raise RuntimeError("Can only add static components to subclasses")

        id_match, custom_id = _internal.gen_custom_id(custom_id)
        field = _StaticField(
            id_match,
            callback,
            hikari.impl.SelectMenuBuilder(
                type=type_,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )
        cls._added_static_fields[custom_id] = field
        cls._static_fields[custom_id] = field
        return cls

    def add_mentionable_menu(
        self,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> Self:
        """Add a mentionable select menu to this action column.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        Self
            The action column to enable chained calls.
        """
        return self.add_select_menu(
            hikari.ComponentType.MENTIONABLE_SELECT_MENU,
            callback,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )

    @typing.overload
    def with_mentionable_menu(self, callback: _CallbackSigT, /) -> _CallbackSigT: ...

    @typing.overload
    def with_mentionable_menu(
        self,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]: ...

    def with_mentionable_menu(
        self,
        callback: typing.Optional[_CallbackSigT] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[_CallbackSigT, collections.Callable[[_CallbackSigT], _CallbackSigT]]:
        """Add a mentionable select menu to this action column through a decorator call.

        Parameters
        ----------
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.
        """
        return _decorate(
            callback,
            lambda callback_: self.add_mentionable_menu(
                callback_,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )

    @classmethod
    def add_static_mentionable_menu(
        cls,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> type[Self]:
        """Add a mentionable select menu to all subclasses and instances of this action column class.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        type[Self]
            The action column class to enable chained calls.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        return cls.add_static_select_menu(
            hikari.ComponentType.MENTIONABLE_SELECT_MENU,
            callback,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )

    @classmethod
    @typing.overload
    def with_static_mentionable_menu(cls, callback: _CallbackSigT, /) -> _CallbackSigT: ...

    @classmethod
    @typing.overload
    def with_static_mentionable_menu(
        cls,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]: ...

    @classmethod
    def with_static_mentionable_menu(
        cls,
        callback: typing.Optional[_CallbackSigT] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[_CallbackSigT, collections.Callable[[_CallbackSigT], _CallbackSigT]]:
        """Add a static mentionable select menu to this action column class through a decorator call.

        Parameters
        ----------
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        return _decorate(
            callback,
            lambda callback_: cls.add_static_mentionable_menu(
                callback_,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )

    def add_role_menu(
        self,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> Self:
        """Add a role select menu to this action column.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        Self
            The action column to enable chained calls.
        """
        return self.add_select_menu(
            hikari.ComponentType.ROLE_SELECT_MENU,
            callback,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )

    @typing.overload
    def with_role_menu(self, callback: _CallbackSigT, /) -> _CallbackSigT: ...

    @typing.overload
    def with_role_menu(
        self,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]: ...

    def with_role_menu(
        self,
        callback: typing.Optional[_CallbackSigT] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[_CallbackSigT, collections.Callable[[_CallbackSigT], _CallbackSigT]]:
        """Add a role select menu to this action column through a decorator call.

        Parameters
        ----------
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.
        """
        return _decorate(
            callback,
            lambda callback_: self.add_role_menu(
                callback_,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )

    @classmethod
    def add_static_role_menu(
        cls,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> type[Self]:
        """Add a role select menu to all subclasses and instances of this action column class.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        type[Self]
            The action column class to enable chained calls.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        return cls.add_static_select_menu(
            hikari.ComponentType.ROLE_SELECT_MENU,
            callback,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )

    @classmethod
    @typing.overload
    def with_static_role_menu(cls, callback: _CallbackSigT, /) -> _CallbackSigT: ...

    @classmethod
    @typing.overload
    def with_static_role_menu(
        cls,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]: ...

    @classmethod
    def with_static_role_menu(
        cls,
        callback: typing.Optional[_CallbackSigT] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[_CallbackSigT, collections.Callable[[_CallbackSigT], _CallbackSigT]]:
        """Add a static role select menu to this action column class through a decorator call.

        Parameters
        ----------
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        return _decorate(
            callback,
            lambda callback_: cls.add_static_role_menu(
                callback_,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )

    def add_user_menu(
        self,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> Self:
        """Add a user select menu to this action column.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        Self
            The action column to enable chained calls.
        """
        return self.add_select_menu(
            hikari.ComponentType.USER_SELECT_MENU,
            callback,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )

    @typing.overload
    def with_user_menu(self, callback: _CallbackSigT, /) -> _CallbackSigT: ...

    @typing.overload
    def with_user_menu(
        self,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]: ...

    def with_user_menu(
        self,
        callback: typing.Optional[_CallbackSigT] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[_CallbackSigT, collections.Callable[[_CallbackSigT], _CallbackSigT]]:
        """Add a user select menu to this action column through a decorator call.

        Parameters
        ----------
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.
        """
        return _decorate(
            callback,
            lambda callback_: self.add_user_menu(
                callback_,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )

    @classmethod
    def add_static_user_menu(
        cls,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> type[Self]:
        """Add a user select menu to all subclasses and instances of this action column class.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        type[Self]
            The action column class to enable chained calls.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        return cls.add_static_select_menu(
            hikari.ComponentType.USER_SELECT_MENU,
            callback,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )

    @classmethod
    @typing.overload
    def with_static_user_menu(cls, callback: _CallbackSigT, /) -> _CallbackSigT: ...

    @classmethod
    @typing.overload
    def with_static_user_menu(
        cls,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]: ...

    @classmethod
    def with_static_user_menu(
        cls,
        callback: typing.Optional[_CallbackSigT] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[_CallbackSigT, collections.Callable[[_CallbackSigT], _CallbackSigT]]:
        """Add a static user select menu to this action column class through a decorator call.

        Parameters
        ----------
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        return _decorate(
            callback,
            lambda callback_: cls.add_static_user_menu(
                callback_,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )

    def add_channel_menu(
        self,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        channel_types: typing.Optional[
            collections.Sequence[typing.Union[hikari.ChannelType, type[hikari.PartialChannel]]]
        ] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> Self:
        """Add a channel select menu to this action column.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        channel_types
            Sequence of the types of channels this select menu should show as options.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        Self
            The action column to enable chained calls.
        """
        id_match, custom_id = _internal.gen_custom_id(custom_id)
        _append_row(self._rows).add_channel_menu(
            custom_id,
            channel_types=_parse_channel_types(*channel_types) if channel_types else [],
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )
        self._callbacks[id_match] = callback
        return self

    @typing.overload
    def with_channel_menu(self, callback: _CallbackSigT, /) -> _CallbackSigT: ...

    @typing.overload
    def with_channel_menu(
        self,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        channel_types: typing.Optional[
            collections.Sequence[typing.Union[hikari.ChannelType, type[hikari.PartialChannel]]]
        ] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]: ...

    def with_channel_menu(
        self,
        callback: typing.Optional[_CallbackSigT] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        channel_types: typing.Optional[
            collections.Sequence[typing.Union[hikari.ChannelType, type[hikari.PartialChannel]]]
        ] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[_CallbackSigT, collections.Callable[[_CallbackSigT], _CallbackSigT]]:
        """Add a channel select menu to this action column through a decorator call.

        Parameters
        ----------
        channel_types
            Sequence of the types of channels this select menu should show as options.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.
        """
        return _decorate(
            callback,
            lambda callback_: self.add_channel_menu(
                callback_,
                custom_id=custom_id,
                channel_types=channel_types,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )

    @classmethod
    def add_static_channel_menu(
        cls,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        channel_types: typing.Optional[
            collections.Sequence[typing.Union[hikari.ChannelType, type[hikari.PartialChannel]]]
        ] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> type[Self]:
        """Add a channel select menu to all subclasses and instances of this action column class.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        channel_types
            Sequence of the types of channels this select menu should show as options.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        type[Self]
            The action column class to enable chained calls.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        if cls is ActionColumnExecutor:
            raise RuntimeError("Can only add static components to subclasses")

        id_match, custom_id = _internal.gen_custom_id(custom_id)
        field = _StaticField(
            id_match,
            callback,
            hikari.impl.ChannelSelectMenuBuilder(
                custom_id=custom_id,
                channel_types=_parse_channel_types(*channel_types) if channel_types else [],
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )
        cls._added_static_fields[custom_id] = field
        cls._static_fields[custom_id] = field
        return cls

    @classmethod
    @typing.overload
    def with_static_channel_menu(cls, callback: _CallbackSigT, /) -> _CallbackSigT: ...

    @classmethod
    @typing.overload
    def with_static_channel_menu(
        cls,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        channel_types: typing.Optional[
            collections.Sequence[typing.Union[hikari.ChannelType, type[hikari.PartialChannel]]]
        ] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]: ...

    @classmethod
    def with_static_channel_menu(
        cls,
        callback: typing.Optional[_CallbackSigT] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        channel_types: typing.Optional[
            collections.Sequence[typing.Union[hikari.ChannelType, type[hikari.PartialChannel]]]
        ] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[_CallbackSigT, collections.Callable[[_CallbackSigT], _CallbackSigT]]:
        """Add a channel select menu to this action column class through a decorator call.

        Parameters
        ----------
        channel_types
            Sequence of the types of channels this select menu should show as options.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        return _decorate(
            callback,
            lambda callback_: cls.add_static_channel_menu(
                callback_,
                custom_id=custom_id,
                channel_types=channel_types,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            ),
        )

    def add_text_menu(
        self,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        options: collections.Sequence[hikari.api.SelectOptionBuilder] = (),
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> hikari.api.TextSelectMenuBuilder[Self]:
        """Add a text select menu to this action column.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        options
            The text select's options.

            These can also be added by calling
            [TextSelectMenuBuilder.add_option][hikari.api.special_endpoints.TextSelectMenuBuilder.add_option].
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        hikari.api.special_endpoints.TextSelectMenuBuilder
            Builder for the added text select menu.

            [TextSelectMenuBuilder.add_option][hikari.api.special_endpoints.TextSelectMenuBuilder.add_option]
            should be used to add options to this select menu.

            And the parent action column can be accessed by calling
            [TextSelectMenuBuilder.parent][hikari.api.special_endpoints.TextSelectMenuBuilder.parent].
        """
        id_match, custom_id = _internal.gen_custom_id(custom_id)
        menu = _TextSelectMenuBuilder(
            parent=self,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
            options=options,
        )
        _append_row(self._rows).add_component(menu)
        self._callbacks[id_match] = callback
        return menu

    @typing.overload
    def with_text_menu(self, callback: collections.Callable[_P, _CoroT], /) -> _WrappedTextMenuBuilder[_P]: ...

    @typing.overload
    def with_text_menu(
        self,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        options: collections.Sequence[hikari.api.SelectOptionBuilder] = (),
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[collections.Callable[_P, _CoroT]], _WrappedTextMenuBuilder[_P]]: ...

    def with_text_menu(
        self,
        callback: typing.Optional[collections.Callable[_P, _CoroT]] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        options: collections.Sequence[hikari.api.SelectOptionBuilder] = (),
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[
        _WrappedTextMenuBuilder[_P],
        collections.Callable[[collections.Callable[_P, _CoroT]], _WrappedTextMenuBuilder[_P]],
    ]:
        """Add a text select menu to this action column through a decorator callback.

        Parameters
        ----------
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        options
            The text select's options.

            These can also be added using [components.with_option][yuyo.components.with_option].
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.
        """
        return _consume(
            callback,
            lambda callback_: _WrappedTextMenuBuilder(
                callback_,
                self.add_text_menu(
                    callback_,
                    custom_id=custom_id,
                    options=options,
                    placeholder=placeholder,
                    min_values=min_values,
                    max_values=max_values,
                    is_disabled=is_disabled,
                ),
            ),
        )

    @classmethod
    def add_static_text_menu(
        cls,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        options: collections.Sequence[hikari.api.SelectOptionBuilder] = (),
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> hikari.api.TextSelectMenuBuilder[type[Self]]:
        """Add a text select menu to all subclasses and instances of this action column class.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        options
            The text select's options.

            These can also be added by calling
            [TextSelectMenuBuilder.add_option][hikari.api.special_endpoints.TextSelectMenuBuilder.add_option].
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Returns
        -------
        hikari.api.special_endpoints.TextSelectMenuBuilder
            Builder for the added text select menu.

            [TextSelectMenuBuilder.add_option][hikari.api.special_endpoints.TextSelectMenuBuilder.add_option]
            should be used to add options to this select menu.

            And the parent action column can be accessed by calling
            [TextSelectMenuBuilder.parent][hikari.api.special_endpoints.TextSelectMenuBuilder.parent].

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        if cls is ActionColumnExecutor:
            raise RuntimeError("Can only add static components to subclasses")

        id_match, custom_id = _internal.gen_custom_id(custom_id)
        component = _TextSelectMenuBuilder(
            parent=cls,
            custom_id=custom_id,
            options=list(options),
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )
        field = _StaticField(id_match, callback, component)
        cls._added_static_fields[custom_id] = field
        cls._static_fields[custom_id] = field
        return component

    @classmethod
    @typing.overload
    def with_static_text_menu(cls, callback: collections.Callable[_P, _CoroT], /) -> _WrappedTextMenuBuilder[_P]: ...

    @classmethod
    @typing.overload
    def with_static_text_menu(
        cls,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        options: collections.Sequence[hikari.api.SelectOptionBuilder] = (),
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[collections.Callable[_P, _CoroT]], _WrappedTextMenuBuilder[_P]]: ...

    @classmethod
    def with_static_text_menu(
        cls,
        callback: typing.Optional[collections.Callable[_P, _CoroT]] = None,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        options: collections.Sequence[hikari.api.SelectOptionBuilder] = (),
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> typing.Union[
        _WrappedTextMenuBuilder[_P],
        collections.Callable[[collections.Callable[_P, _CoroT]], _WrappedTextMenuBuilder[_P]],
    ]:
        """Add a text select menu to this action column class through a decorator call.

        Parameters
        ----------
        custom_id
            The select menu's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.

            Only `custom_id.split(":", 1)[0]` will be used to match against
            interactions. Anything after `":"` is metadata.
        options
            The text select's options.

            These can also be added using [yuyo.components.with_option].
        placeholder
            Placeholder text to show when no entries have been selected.
        min_values
            The minimum amount of entries which need to be selected.
        max_values
            The maximum amount of entries which can be selected.
        is_disabled
            Whether this select menu should be marked as disabled.

        Raises
        ------
        RuntimeError
            When called directly on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """
        return _consume(
            callback,
            lambda callback_: _WrappedTextMenuBuilder(
                callback_,
                cls.add_static_text_menu(
                    callback_,
                    custom_id=custom_id,
                    options=options,
                    placeholder=placeholder,
                    min_values=min_values,
                    max_values=max_values,
                    is_disabled=is_disabled,
                ),
            ),
        )


# TODO: maybe don't use paramspec here
class _WrappedTextMenuBuilder(typing.Generic[_P]):
    def __init__(
        self, callback: collections.Callable[_P, _CoroT], builder: hikari.api.TextSelectMenuBuilder[typing.Any], /
    ) -> None:
        self._builder = builder
        self._callback = callback
        functools.update_wrapper(self, callback)

    async def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> None:
        return await self._callback(*args, **kwargs)

    def add_option(
        self,
        label: str,
        value: str,
        /,
        *,
        description: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        is_default: bool = False,
    ) -> Self:
        self._builder.add_option(label, value, description=description, emoji=emoji, is_default=is_default)
        return self


def _row_is_full(row: hikari.api.MessageActionRowBuilder) -> bool:
    components = row.components
    if components and isinstance(components[0], hikari.api.ButtonBuilder):
        return len(components) >= 5

    return bool(components)


def _append_row(
    rows: list[hikari.api.MessageActionRowBuilder], /, *, is_button: bool = False
) -> hikari.api.MessageActionRowBuilder:
    if not rows or _row_is_full(rows[-1]):
        row = hikari.impl.MessageActionRowBuilder()
        rows.append(row)
        return row

    # This works since the other types all take up the whole row right now.
    if is_button or not rows[-1].components:
        return rows[-1]

    row = hikari.impl.MessageActionRowBuilder()
    rows.append(row)
    return row


def column_template(ephemeral_default: bool = False) -> type[ActionColumnExecutor]:
    """Create a column template through a decorator callback.

    The returned type acts like any other slotted action column subclass and
    supports the same `add_static` class methods and initialisation signature.

    Parameters
    ----------
    ephemeral_default
        Whether this column template's responses should default to ephemeral.

    Returns
    -------
    type[ActionColumnExecutor]
        The new column template.
    """
    _ephemeral_default = ephemeral_default
    del ephemeral_default

    class Column(ActionColumnExecutor):
        __slots__ = ()

        def __init__(
            self,
            *,
            ephemeral_default: bool = _ephemeral_default,
            id_metadata: typing.Optional[collections.Mapping[str, str]] = None,
        ) -> None:
            super().__init__(ephemeral_default=ephemeral_default, id_metadata=id_metadata)

    return Column


class ComponentPaginator(ActionColumnExecutor):
    """Standard implementation of an action row executor used for pagination.

    This is a convenience class that allows you to easily implement a paginator.

    !!! note
        This doesn't use action column's "static" components so any static
        components added to base-classes of this will appear before the
        pagination components.
    """

    __slots__ = ("_lock", "_paginator")

    def __init__(
        self,
        iterator: _internal.IteratorT[pagination.EntryT],
        /,
        *,
        authors: typing.Optional[collections.Iterable[hikari.SnowflakeishOr[hikari.User]]] = None,
        ephemeral_default: bool = False,
        triggers: collections.Collection[str] = (
            pagination.LEFT_TRIANGLE,
            pagination.STOP_SQUARE,
            pagination.RIGHT_TRIANGLE,
        ),
    ) -> None:
        """Initialise a component paginator.

        Parameters
        ----------
        iterator : collections.Iterator[yuyo.pagination.EntryT] | collections.AsyncIterator[yuyo.pagination.EntryT]
            The iterator to paginate.

            This should be an iterator of [yuyo.pagination.AbstractPage][]s.
        authors
            Users who are allowed to use the components this represents.

            If no users are provided then the components will be public
            (meaning that anybody can use it).
        ephemeral_default
            Whether or not the responses made on contexts spawned from this paginator
            should default to ephemeral (meaning only the author can see them) unless
            `flags` is specified on the response method.
        triggers
            Collection of the unicode emojis that should trigger this paginator.

            As of current the only usable emojis are [yuyo.pagination.LEFT_TRIANGLE][],
            [yuyo.pagination.RIGHT_TRIANGLE][], [yuyo.pagination.STOP_SQUARE][],
            [yuyo.pagination.LEFT_DOUBLE_TRIANGLE][] and [yuyo.pagination.LEFT_TRIANGLE][].
        """
        if not isinstance(
            iterator, (collections.Iterator, collections.AsyncIterator)
        ):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"Invalid value passed for `iterator`, expected an iterator but got {type(iterator)}")

        super().__init__(authors=authors, ephemeral_default=ephemeral_default)

        self._lock = asyncio.Lock()
        self._paginator = pagination.Paginator(iterator)

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

    def add_first_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.SECONDARY,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[
            hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType
        ] = pagination.LEFT_DOUBLE_TRIANGLE,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the jump to first entry button to this paginator.

        You should pass `triggers=[]` to
        [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        custom_id
            Custom ID to use for identifying button presses.
        emoji
            Emoji to display on this button.
        label
            Label to display on this button.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style, self._on_first, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
        )

    def add_previous_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.SECONDARY,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = pagination.LEFT_TRIANGLE,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the previous entry button to this paginator.

        You should pass `triggers=[]` to
        [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        custom_id
            Custom ID to use for identifying button presses.
        emoji
            Emoji to display on this button.

            Either this or `label` must be provided, but not both.
        label
            Label to display on this button.

            Either this or `emoji` must be provided, but not both.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style, self._on_previous, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
        )

    def add_stop_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.DANGER,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = pagination.BLACK_CROSS,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the stop button to this paginator.

        You should pass `triggers=[]` to
        [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        custom_id
            Custom ID to use for identifying button presses.
        emoji
            Emoji to display on this button.

            Either this or `label` must be provided, but not both.
        label
            Label to display on this button.

            Either this or `emoji` must be provided, but not both.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style, self._on_disable, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
        )

    def add_next_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.SECONDARY,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = pagination.RIGHT_TRIANGLE,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the next entry button to this paginator.

        You should pass `triggers=[]` to
        [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        custom_id
            Custom ID to use for identifying button presses.
        emoji
            Emoji to display on this button.

            Either this or `label` must be provided, but not both.
        label
            Label to display on this button.

            Either this or `emoji` must be provided, but not both.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style, self._on_next, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
        )

    def add_last_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.SECONDARY,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[
            hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType
        ] = pagination.RIGHT_DOUBLE_TRIANGLE,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the jump to last entry button to this paginator.

        You should pass `triggers=[]` to
        [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        custom_id
            Custom ID to use for identifying button presses.
        emoji
            Emoji to display on this button.

            Either this or `label` must be provided, but not both.
        label
            Label to display on this button.

            Either this or `emoji` must be provided, but not both.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style, self._on_last, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
        )

    async def execute(self, ctx: Context, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        ctx.set_ephemeral_default(self._ephemeral_default)
        if self._authors and ctx.interaction.user.id not in self._authors:
            await ctx.create_initial_response("You are not allowed to use this component", ephemeral=True)
            return

        await super().execute(ctx)

    async def get_next_entry(self) -> typing.Optional[pagination.AbstractPage]:
        """Get the next entry in this paginator.

        This is generally helpful for making the message which the paginator will be based off
        and will still internally store the entry and increment the position of the paginator.

        Examples
        --------
        ```py
        paginator = yuyo.ComponentPaginator(pages, authors=[ctx.author.id])
        first_response = await paginator.get_next_entry()
        assert first_response
        message = await ctx.respond(components=paginator.rows, **first_response.to_kwargs(), ensure_result=True)
        component_client.register_executor(paginator, message=message)
        ```

        Returns
        -------
        yuyo.pagination.AbstractPage | None
            The next entry in this paginator, or [None][] if there are no more entries.
        """
        return await self._paginator.step_forward()

    async def _on_first(self, ctx: Context, /) -> None:
        if page := self._paginator.jump_to_first():
            await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, **page.to_kwargs())

        else:
            await _noop(ctx)

    async def _on_previous(self, ctx: Context, /) -> None:
        if page := self._paginator.step_back():
            await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, **page.to_kwargs())

        else:
            await _noop(ctx)

    async def _on_disable(self, ctx: Context, /) -> None:
        self._paginator.close()
        await ctx.defer(defer_type=hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
        await ctx.delete_initial_response()
        raise ExecutorClosed(already_closed=False)

    async def _on_last(self, ctx: Context, /) -> None:
        deferring = not self._paginator.has_finished_iterating
        if deferring:
            # TODO: option to not lock on last
            loading_component = ctx.interaction.app.rest.build_message_action_row().add_interactive_button(
                hikari.ButtonStyle.SECONDARY, "loading", is_disabled=True, emoji=878377505344614461
            )
            await ctx.create_initial_response(
                component=loading_component, response_type=hikari.ResponseType.MESSAGE_UPDATE
            )

        if page := await self._paginator.jump_to_last():
            if deferring:
                await ctx.edit_initial_response(components=self.rows, **page.to_kwargs())

            else:
                await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, **page.to_kwargs())

        elif deferring:  # Just edit back in the old components without changing the content
            await ctx.edit_initial_response(components=self.rows)

        else:  # Avoid changing the content as there are no-more pages.
            await _noop(ctx)

    async def _on_next(self, ctx: Context, /) -> None:
        if page := await self._paginator.step_forward():
            await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, **page.to_kwargs())

        else:
            await _noop(ctx)


Paginator = ComponentPaginator
"""Alias of [ComponentPaginator][yuyo.components.ComponentPaginator]."""


STATIC_PAGINATION_ID = "yuyo.pag"
_INDEX_ID_KEY = "id"
_PAGE_NUMBER_KEY = "index"
_HASH_INDEX_KEY = "hash"


class StaticPaginatorData:
    """Represents a static paginator's data."""

    __slots__ = ("_content_hash", "_make_components", "_pages", "_paginator_id")

    def __init__(
        self,
        paginator_id: str,
        pages: collections.Sequence[pagination.AbstractPage],
        /,
        *,
        content_hash: typing.Optional[str],
        make_components: collections.Callable[
            [str, int, typing.Optional[str]], ActionColumnExecutor
        ] = lambda paginator_id, page_number, content_hash: StaticComponentPaginator(
            paginator_id, page_number, content_hash=content_hash
        ),
    ) -> None:
        """Initialise a static paginator.

        Parameters
        ----------
        pages
            Sequence of the static paginator's pages.
        content_hash
            Optional hash used to verify data sync.
        """
        self._content_hash = content_hash
        self._make_components = make_components
        self._pages = pages
        self._paginator_id = paginator_id

    @property
    def content_hash(self) -> typing.Optional[str]:
        """Optional hash used to verify data sync."""
        return self._content_hash

    @property
    def pages(self) -> collections.Sequence[pagination.AbstractPage]:
        """The paginator's pages."""
        return self._pages

    def get_page(self, page_number: int, /) -> typing.Optional[pagination.AbstractPage]:
        """Get a page from the paginator.

        Parameters
        ----------
        page_number
            The zero-indexed page index.

        Returns
        -------
        yuyo.pagination.AbstractPage | None
            The found page or None if out of bounds.
        """
        try:
            return self._pages[page_number]

        except IndexError:
            return None

    def make_components(self, page_number: int, /) -> ActionColumnExecutor:
        """Make the base message components used to start a paginted message.

        Parameters
        ----------
        page_number
            Index of the starting page.

        Returns
        -------
        yuyo.components.ActionColumnExecutor
            The created acion column execugtor.

        Raises
        ------
        KeyError
            If paginator_id isn't found.
        """
        return self._make_components(self._paginator_id, page_number, self._content_hash)


def static_paginator_model(
    *, invalid_number_response: typing.Optional[pagination.AbstractPage] = None, field_label: str = "Page number"
) -> modals.Modal:
    """Create a default implementation of the modal used for static paginator page jumping.

    Parameters
    ----------
    invalid_number_response
        The response to send when an invalid number is input.
    field_label
        Label to show for the number input field.

    Returns
    -------
    models.Modal
        The created modal.
    """
    invalid_number_response = invalid_number_response or pagination.Page("Not a valid number")

    @modals.as_modal(parse_signature=True)
    async def modal(
        ctx: modals.ModalContext,
        /,
        *,
        field: str = modals.text_input(field_label, custom_id=STATIC_PAGINATION_ID, min_length=1),
        index: alluka.Injected[StaticPaginatorIndex],
    ) -> None:
        try:
            page_number = int(field)
        except ValueError:
            page_number = -1

        if page_number < 1:
            raise interactions.InteractionError(**invalid_number_response.ctx_to_kwargs(ctx))

        await index.callback(ctx, page_number - 1)

    return modal


@dataclasses.dataclass
class _Metadata:
    paginator_id: str
    content_hash: typing.Optional[str]
    page_number: typing.Optional[int]


def _parse_metadata(raw_metadata: str, /) -> _Metadata:
    metadata = urllib.parse.parse_qs(raw_metadata)
    paginator_id = metadata[_INDEX_ID_KEY][0]

    try:
        content_hash = metadata[_HASH_INDEX_KEY][0]

    except (KeyError, IndexError):
        content_hash = None

    try:  # noqa: TRY101
        page_number = int(metadata[_PAGE_NUMBER_KEY][0])

    except (KeyError, IndexError):
        page_number = None

    return _Metadata(content_hash=content_hash, paginator_id=paginator_id, page_number=page_number)


class _StaticPaginatorId(str, enum.Enum):
    FIRST = f"{STATIC_PAGINATION_ID}.first"
    PREVIOUS = f"{STATIC_PAGINATION_ID}.prev"
    SELECT = f"{STATIC_PAGINATION_ID}.select"
    NEXT = f"{STATIC_PAGINATION_ID}.next"
    LAST = f"{STATIC_PAGINATION_ID}.last"


_STATIC_BACKWARDS_BUTTONS = {_StaticPaginatorId.FIRST, _StaticPaginatorId.PREVIOUS}
_STATIC_FORWARD_BUTTONS = {_StaticPaginatorId.NEXT, _StaticPaginatorId.LAST}


def _get_page_number(ctx: ComponentContext, /) -> int:
    metadata = _parse_metadata(ctx.id_metadata)
    if metadata.page_number is None:
        raise RuntimeError("Missing page number in ID metadata")

    return metadata.page_number


class StaticComponentPaginator(ActionColumnExecutor):
    """Implementation of components for paginating static data.

    This enables paginated responses to be persisted between bot restarts.
    """

    __slots__ = ("_metadata",)

    def __init__(
        self,
        paginator_id: str,
        page_number: int,
        /,
        *,
        content_hash: typing.Optional[str] = None,
        ephemeral_default: bool = False,
        include_buttons: bool = True,
        id_metadata: collections.Mapping[str, str] | None = None,
    ) -> None:
        """Initialise a static component paginator.

        Parameters
        ----------
        paginator_id
            ID of the paginator this targets.

            This is ignored when this is used to execute interactions.
        page_number
            Index of the current page this paginator is on.

            This is ignored when this is used to execute interactions.
        content_hash
            Hash used to validate that the received interaction's components
            are still in-sync with the static data stored in this paginator.
        ephemeral_default
            Whether this executor's responses should default to being ephemeral.
        include_buttons
            Whether to include the default buttons.
        id_metadata
            Mapping of metadata to append to the custom IDs in this column.

            This does not effect the standard buttons.
        """
        super().__init__(ephemeral_default=ephemeral_default, id_metadata=id_metadata)
        self._metadata: dict[str, str] = {_INDEX_ID_KEY: paginator_id, _PAGE_NUMBER_KEY: str(page_number)}

        if content_hash is not None:
            self._metadata[_HASH_INDEX_KEY] = content_hash

        if include_buttons:
            self.add_first_button().add_previous_button().add_select_button().add_next_button().add_last_button()

    def _to_custom_id(
        self, custom_id: str, id_metadata: typing.Optional[collections.Mapping[str, str]] = None, /
    ) -> str:
        if id_metadata:
            id_metadata = dict(id_metadata)
            id_metadata.update(self._metadata)

        else:
            id_metadata = self._metadata

        return f"{custom_id}:{urllib.parse.urlencode(id_metadata)}"

    def add_first_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.SECONDARY,
        custom_id: str = _StaticPaginatorId.FIRST,
        emoji: typing.Union[
            hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType
        ] = pagination.LEFT_DOUBLE_TRIANGLE,
        id_metadata: typing.Optional[collections.Mapping[str, str]] = None,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the jump to first entry button to this paginator.

        You should pass `include_buttons=False` to
        [StaticComponentPaginator.\_\_init\_\_][yuyo.components.StaticComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        emoji
            Emoji to display on this button.
        id_metadata
            Mapping of keys to the values of extra metadata to
            include in this button's custom ID.

            This will be encoded as a url query string.
        label
            Label to display on this button.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style,
            self._on_first,
            custom_id=self._to_custom_id(custom_id, id_metadata),
            emoji=emoji,
            label=label,
            is_disabled=is_disabled,
        )

    def add_previous_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.SECONDARY,
        custom_id: str = _StaticPaginatorId.PREVIOUS,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = pagination.LEFT_TRIANGLE,
        id_metadata: typing.Optional[collections.Mapping[str, str]] = None,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the previous entry button to this paginator.

        You should pass `include_buttons=False` to
        [StaticComponentPaginator.\_\_init\_\_][yuyo.components.StaticComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        emoji
            Emoji to display on this button.

            Either this or `label` must be provided, but not both.
        id_metadata
            Mapping of keys to the values of extra metadata to
            include in this button's custom ID.

            This will be encoded as a url query string.
        label
            Label to display on this button.

            Either this or `emoji` must be provided, but not both.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style,
            self._on_previous,
            custom_id=self._to_custom_id(custom_id, id_metadata),
            emoji=emoji,
            label=label,
            is_disabled=is_disabled,
        )

    def add_select_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.DANGER,
        custom_id: str = _StaticPaginatorId.SELECT,
        emoji: typing.Union[
            hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType
        ] = pagination.SELECT_PAGE_SYMBOL,
        id_metadata: typing.Optional[collections.Mapping[str, str]] = None,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the select page button to this paginator.

        You should pass `include_buttons=False` to
        [StaticComponentPaginator.\_\_init\_\_][yuyo.components.StaticComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        emoji
            Emoji to display on this button.

            Either this or `label` must be provided, but not both.
        id_metadata
            Mapping of keys to the values of extra metadata to
            include in this button's custom ID.

            This will be encoded as a url query string.
        label
            Label to display on this button.

            Either this or `emoji` must be provided, but not both.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style,
            self._on_select,
            custom_id=self._to_custom_id(custom_id, id_metadata),
            emoji=emoji,
            label=label,
            is_disabled=is_disabled,
        )

    def add_next_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.SECONDARY,
        custom_id: str = _StaticPaginatorId.NEXT,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = pagination.RIGHT_TRIANGLE,
        id_metadata: typing.Optional[collections.Mapping[str, str]] = None,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the next entry button to this paginator.

        You should pass `include_buttons=False` to
        [StaticComponentPaginator.\_\_init\_\_][yuyo.components.StaticComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        emoji
            Emoji to display on this button.

            Either this or `label` must be provided, but not both.
        id_metadata
            Mapping of keys to the values of extra metadata to
            include in this button's custom ID.

            This will be encoded as a url query string.
        label
            Label to display on this button.

            Either this or `emoji` must be provided, but not both.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style,
            self._on_next,
            custom_id=self._to_custom_id(custom_id, id_metadata),
            emoji=emoji,
            label=label,
            is_disabled=is_disabled,
        )

    def add_last_button(
        self,
        *,
        style: hikari.InteractiveButtonTypesT = hikari.ButtonStyle.SECONDARY,
        custom_id: str = _StaticPaginatorId.LAST,
        emoji: typing.Union[
            hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType
        ] = pagination.RIGHT_DOUBLE_TRIANGLE,
        id_metadata: typing.Optional[collections.Mapping[str, str]] = None,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        r"""Add the jump to last entry button to this paginator.

        You should pass `include_buttons=False` to
        [StaticComponentPaginator.\_\_init\_\_][yuyo.components.StaticComponentPaginator.__init__]
        before calling this.

        !!! note
            These buttons will appear in the order these methods were called in.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        emoji
            Emoji to display on this button.

            Either this or `label` must be provided, but not both.
        id_metadata
            Mapping of keys to the values of extra metadata to
            include in this button's custom ID.

            This will be encoded as a url query string.
        label
            Label to display on this button.

            Either this or `emoji` must be provided, but not both.
        is_disabled
            Whether to make this button as disabled.

        Returns
        -------
        Self
            To enable chained calls.
        """
        # Just convenience to let ppl override label without having to unset the default for emoji.
        if label is not hikari.UNDEFINED:
            emoji = hikari.UNDEFINED

        return self.add_interactive_button(
            style,
            self._on_last,
            custom_id=self._to_custom_id(custom_id, id_metadata),
            emoji=emoji,
            label=label,
            is_disabled=is_disabled,
        )

    async def _on_first(self, ctx: ComponentContext, /, *, index: alluka.Injected[StaticPaginatorIndex]) -> None:
        await index.callback(ctx, 0)

    async def _on_previous(self, ctx: ComponentContext, /, *, index: alluka.Injected[StaticPaginatorIndex]) -> None:
        page_number = _get_page_number(ctx)

        if page_number > 0:
            page_number -= 1

        await index.callback(ctx, page_number)

    async def _on_select(self, ctx: ComponentContext, /, *, index: alluka.Injected[StaticPaginatorIndex]) -> None:
        await index.create_select_modal(ctx)

    async def _on_next(self, ctx: ComponentContext, /, *, index: alluka.Injected[StaticPaginatorIndex]) -> None:
        page_number = _get_page_number(ctx)
        await index.callback(ctx, page_number + 1)

    async def _on_last(self, ctx: ComponentContext, /, *, index: alluka.Injected[StaticPaginatorIndex]) -> None:
        await index.callback(ctx, -1)


def _noop(ctx: Context, /) -> _CoroT:
    """Create a noop initial response to a component context."""
    return ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE)


class StaticPaginatorIndex:
    """Index of all the static paginators within a bot."""

    __slots__ = (
        "_make_components",
        "_make_modal",
        "_modal_title",
        "_not_found_response",
        "_out_of_date_response",
        "_paginators",
    )

    def __init__(
        self,
        *,
        make_components: collections.Callable[
            [str, int, typing.Optional[str]], ActionColumnExecutor
        ] = lambda paginator_id, page_number, content_hash: StaticComponentPaginator(
            paginator_id, page_number, content_hash=content_hash
        ),
        make_modal: collections.Callable[[], modals.Modal] = static_paginator_model,
        modal_title: localise.MaybeLocalsiedType[str] = "Select page",
        not_found_response: typing.Optional[pagination.AbstractPage] = None,
        out_of_date_response: typing.Optional[pagination.AbstractPage] = None,
    ) -> None:
        """Initialise a static paginator index.

        Parameters
        ----------
        make_components
            Callback that's used to make the default pagination
            message components.
        make_modal
            Callback that's used to make a modal that handles the
            select page button.
        modal_title
            Title of the modal that's sent when the select page button
            is pressed.
        not_found_response
            The response to send when a paginator ID isn't found.
        out_of_date_response
            The response to send when the content hashes don't match.
        """
        self._make_components = make_components
        self._make_modal = make_modal
        self._modal_title = localise.MaybeLocalised[str].parse("Modal title", modal_title)
        self._not_found_response = not_found_response or pagination.Page("Page not found")
        self._out_of_date_response = out_of_date_response or pagination.Page("This response is out of date")
        self._paginators: dict[str, StaticPaginatorData] = {}

    @property
    def not_found_response(self) -> pagination.AbstractPage:
        """Response that's sent by the default implementation when a paginator ID isn't found."""
        return self._not_found_response

    @property
    def out_of_date_response(self) -> pagination.AbstractPage:
        """Response that's sent by the default implementation when content hashes don't match."""
        return self._out_of_date_response

    def add_to_clients(self, component_client: ComponentClient, modal_client: modals.ModalClient, /) -> Self:
        """Add this index to the component and modal clients to enable operation.

        Parameters
        ----------
        component_client
            The component client to add this to.
        modal_client
            The modal client to add this to.
        """
        component_client.alluka.set_type_dependency(StaticPaginatorIndex, self)
        modal_client.alluka.set_type_dependency(StaticPaginatorIndex, self)
        component_client.register_executor(StaticComponentPaginator("", 0), timeout=None)
        modal_client.register_modal(STATIC_PAGINATION_ID, static_paginator_model(), timeout=None)
        return self

    def set_paginator(
        self,
        paginator_id: str,
        pages: collections.Sequence[pagination.AbstractPage],
        /,
        *,
        content_hash: typing.Optional[str] = None,
    ) -> Self:
        """Set the static paginator for a custom ID.

        Parameters
        ----------
        paginator_id
            ID that's used to identify this paginator.
        pages
            Sequence of the paginator's built pages.
        content_hash
            Content hash that's used to optionally ensure instances of the
            of the paginator's components are compatible with the bot's stored data.

        Raises
        ------
        ValueError
            If `paginator_id` is already set.
        """
        if paginator_id in self._paginators:
            raise ValueError("Paginator already set")

        self._paginators[paginator_id] = StaticPaginatorData(
            paginator_id, pages, content_hash=content_hash, make_components=self._make_components
        )
        return self

    def get_paginator(self, paginator_id: str, /) -> StaticPaginatorData:
        """Get a paginator.

        Parameters
        ----------
        paginator_id
            ID of the paginator to get.

        Returns
        -------
        yuyo.components.StaticPaginatorData
            The found static paginator.

        Raises
        ------
        KeyError
            If no paginator was found.
        """
        return self._paginators[paginator_id]

    def remove_paginator(self, paginator_id: str, /) -> Self:
        """Remove a static paginator.

        Parameters
        ----------
        paginator_id
            ID of the paginator to remove.

        Raises
        ------
        KeyError
            If no paginator was found.
        """
        del self._paginators[paginator_id]
        return self

    async def callback(
        self,
        ctx: typing.Union[
            interactions.BaseContext[hikari.ComponentInteraction], interactions.BaseContext[hikari.ModalInteraction]
        ],
        page_number: int,
        /,
    ) -> None:
        """Execute a static paginator interaction.

        Parameters
        ----------
        ctx
            The context of the component or modal interaction being executed.
        page_number
            The paginator instance's current page.
        """
        metadata = _parse_metadata(ctx.id_metadata)

        try:
            paginator = self.get_paginator(metadata.paginator_id)

        except KeyError:
            raise RuntimeError(f"Unknown paginator {metadata.paginator_id}") from None

        if paginator.content_hash and paginator.content_hash != metadata.content_hash:
            await ctx.create_initial_response(ephemeral=True, **self.out_of_date_response.ctx_to_kwargs(ctx))

        elif page := paginator.get_page(page_number):
            last_index = len(paginator.pages) - 1
            if page_number == -1:
                page_number = last_index

            components = paginator.make_components(page_number).rows
            if page_number == last_index or page_number == 0:
                for component in _iter_components(components):
                    if not isinstance(component, hikari.api.InteractiveButtonBuilder):
                        continue

                    custom_id = component.custom_id.split(":", 1)[0]
                    if (
                        page_number == 0
                        and custom_id in _STATIC_BACKWARDS_BUTTONS
                        or page_number == last_index
                        and custom_id in _STATIC_FORWARD_BUTTONS
                    ):
                        component.set_is_disabled(True)

            await ctx.create_initial_response(
                response_type=hikari.ResponseType.MESSAGE_UPDATE, components=components, **page.ctx_to_kwargs(ctx)
            )

        else:
            await ctx.create_initial_response(ephemeral=True, **self.not_found_response.ctx_to_kwargs(ctx))

    async def create_select_modal(self, ctx: ComponentContext, /) -> None:
        """Create the standard modal used to handle the select page button.

        Parameters
        ----------
        ctx
            The component context this modal is being made for.
        """
        await ctx.create_modal_response(
            self._modal_title.localise(ctx),
            f"{STATIC_PAGINATION_ID}:{ctx.id_metadata}",
            components=self._make_modal().rows,
        )


StaticPaginator = StaticComponentPaginator
"""Alias of [StaticComponentPaginator][yuyo.components.StaticComponentPaginator]."""


def _iter_components(
    rows: collections.Sequence[hikari.api.MessageActionRowBuilder],
) -> collections.Iterable[hikari.api.ComponentBuilder]:
    return itertools.chain.from_iterable(row.components for row in rows)


BaseContext = interactions.BaseContext
"""Deprecated alias of [yuyo.interactions.BaseContext][]"""
