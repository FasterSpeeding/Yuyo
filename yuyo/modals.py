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
"""Higher level client for modal execution."""
from __future__ import annotations

__all__ = [
    "Modal",
    "ModalClient",
    "ModalContext",
    "ModalOptions",
    "as_modal",
    "as_modal_template",
    "modal",
    "text_input",
    "with_static_text_input",
    "with_text_input",
]

import abc
import asyncio
import collections
import collections.abc
import datetime
import enum
import functools
import itertools
import types
import typing

import alluka as alluka_
import hikari
import typing_extensions

from . import _internal
from . import components as components_
from . import timeouts
from ._internal import inspect

_P = typing_extensions.ParamSpec("_P")
_T = typing.TypeVar("_T")

if typing.TYPE_CHECKING:
    import tanjun
    from typing_extensions import Self

    _ModalT = typing.TypeVar("_ModalT", bound="Modal")
    __SelfishSig = typing_extensions.Concatenate[_T, _P]
    _SelfishSig = __SelfishSig[_T, ...]


_CoroT = collections.abc.Coroutine[typing.Any, typing.Any, _T]

_ModalResponseT = typing.Union[hikari.api.InteractionMessageBuilder, hikari.api.InteractionDeferredBuilder]
"""Type hint of the builder response types allows for modal interactions."""

AbstractTimeout = timeouts.AbstractTimeout
"""Deprecated alias of [yuyo.timeouts.AbstractTimeout][]."""

BasicTimeout = timeouts.BasicTimeout
"""Deprecated alias of [yuyo.timeouts.BasicTimeout][]."""

NeverTimeout = timeouts.NeverTimeout
"""Deprecated alias of [yuyo.timeouts.NeverTimeout][]."""


class _NoDefaultEnum(enum.Enum):
    VALUE = object()


NO_DEFAULT = _NoDefaultEnum.VALUE
"""Singleton used to signify when a field has no default."""

NoDefault = typing.Literal[_NoDefaultEnum.VALUE]
"""Type of [yuyo.modals.NO_DEFAULT][]."""


class ModalContext(components_.BaseContext[hikari.ModalInteraction]):
    """The context used for modal triggers."""

    __slots__ = ("_client",)

    def __init__(
        self,
        client: ModalClient,
        interaction: hikari.ModalInteraction,
        register_task: collections.abc.Callable[[asyncio.Task[typing.Any]], None],
        *,
        ephemeral_default: bool = False,
        response_future: typing.Optional[asyncio.Future[_ModalResponseT]] = None,
    ) -> None:
        super().__init__(
            interaction, register_task, ephemeral_default=ephemeral_default, response_future=response_future
        )
        self._client = client
        self._response_future = response_future

    @property
    def client(self) -> ModalClient:
        """The modal this context is bound to."""
        return self._client

    async def create_initial_response(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
        ephemeral: bool = False,
        attachment: hikari.UndefinedOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedOr[collections.abc.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[collections.abc.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[collections.abc.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: typing.Union[
            hikari.SnowflakeishSequence[hikari.PartialUser], bool, hikari.UndefinedType
        ] = hikari.UNDEFINED,
        role_mentions: typing.Union[
            hikari.SnowflakeishSequence[hikari.PartialRole], bool, hikari.UndefinedType
        ] = hikari.UNDEFINED,
        flags: typing.Union[int, hikari.MessageFlag, hikari.UndefinedType] = hikari.UNDEFINED,
        tts: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
    ) -> None:
        """Create the initial response for this context.

        !!! warning
            Calling this on a context which already has an initial response
            will result in this raising a [hikari.errors.NotFoundError][].
            This includes if the REST interaction server has already responded
            to the request and deferrals.

        Parameters
        ----------
        content
            The content to edit the last response with.

            If provided, the message contents. If
            [hikari.undefined.UNDEFINED][], then nothing will be sent
            in the content. Any other value here will be cast to a
            [str][].

            If this is a [hikari.embeds.Embed][] and no `embed` nor `embeds` kwarg
            is provided, then this will instead update the embed. This allows
            for simpler syntax when sending an embed alone.

            Likewise, if this is a [hikari.files.Resource][], then the
            content is instead treated as an attachment if no `attachment` and
            no `attachments` kwargs are provided.
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Slash command responses can only be deleted within 15 minutes of the
            command being received.
        ephemeral
            Whether the deferred response should be ephemeral.

            Passing [True][] here is a shorthand for including `1 << 64` in the
            passed flags.
        content
            If provided, the message contents. If
            [hikari.undefined.UNDEFINED][], then nothing will be sent
            in the content. Any other value here will be cast to a
            `str`.

            If this is a [hikari.embeds.Embed][] and no `embed` nor `embeds` kwarg
            is provided, then this will instead update the embed. This allows
            for simpler syntax when sending an embed alone.
        attachment
            If provided, the message attachment. This can be a resource,
            or string of a path on your computer or a URL.
        attachments
            If provided, the message attachments. These can be resources, or
            strings consisting of paths on your computer or URLs.
        component
            If provided, builder object of the component to include in this message.
        components
            If provided, a sequence of the component builder objects to include
            in this message.
        embed
            If provided, the message embed.
        embeds
            If provided, the message embeds.
        flags
            If provided, the message flags this response should have.

            As of writing the only message flag which can be set here is
            [hikari.messages.MessageFlag.EPHEMERAL][].
        tts
            If provided, whether the message will be read out by a screen
            reader using Discord's TTS (text-to-speech) system.
        mentions_everyone
            If provided, whether the message should parse @everyone/@here
            mentions.
        user_mentions
            If provided, and [True][], all user mentions will be detected.
            If provided, and [False][], all user mentions will be ignored
            if appearing in the message body.

            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake][], or [hikari.users.PartialUser][]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all role mentions will be detected.
            If provided, and [False][], all role mentions will be ignored
            if appearing in the message body.

            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake], or [hikari.guilds.PartialRole][]
            derivatives to enforce mentioning specific roles.

        Raises
        ------
        ValueError
            If more than 100 unique objects/entities are passed for
            `role_mentions` or `user_mentions`.

            If the interaction will have expired before `delete_after` is reached.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        hikari.BadRequestError
            This may be raised in several discrete situations, such as messages
            being empty with no embeds; messages with more than
            2000 characters in them, embeds that exceed one of the many embed
            limits; invalid image URLs in embeds.
        hikari.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.NotFoundError
            If the interaction is not found or if the interaction's initial
            response has already been created.
        hikari.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        if ephemeral:
            flags = (flags or hikari.MessageFlag.NONE) | hikari.MessageFlag.EPHEMERAL

        async with self._response_lock:
            await self._create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                delete_after=delete_after,
                content=content,
                attachment=attachment,
                attachments=attachments,
                component=component,
                components=components,
                embed=embed,
                embeds=embeds,
                mentions_everyone=mentions_everyone,
                user_mentions=user_mentions,
                role_mentions=role_mentions,
                flags=flags,
                tts=tts,
            )

    async def defer(
        self,
        *,
        ephemeral: bool = False,
        flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag] = hikari.UNDEFINED,
    ) -> None:
        """Defer the initial response for this context.

        !!! note
            The ephemeral state of the first response is decided by whether the
            deferral is ephemeral.

        Parameters
        ----------
        ephemeral
            Whether the deferred response should be ephemeral.

            Passing [True][] here is a shorthand for including `1 << 64` in the
            passed flags.
        flags
            The flags to use for the initial response.
        """
        if ephemeral:
            flags = (flags or hikari.MessageFlag.NONE) | hikari.MessageFlag.EPHEMERAL

        else:
            flags = self._get_flags(flags)

        async with self._response_lock:
            if self._has_been_deferred:
                raise RuntimeError("Context has already been responded to")

            self._has_been_deferred = True
            if self._response_future:
                self._response_future.set_result(self._interaction.build_deferred_response().set_flags(flags))

            else:
                await self._interaction.create_initial_response(
                    hikari.ResponseType.DEFERRED_MESSAGE_CREATE, flags=flags
                )


Context = ModalContext
"""Alias of [ModalContext][yuyo.modals.ModalContext]."""


class ModalClient:
    """Client used to handle modals within a REST or gateway flow."""

    __slots__ = ("_alluka", "_modals", "_event_manager", "_gc_task", "_prefix_ids", "_server", "_tasks")

    def __init__(
        self,
        *,
        alluka: typing.Optional[alluka_.abc.Client] = None,
        event_manager: typing.Optional[hikari.api.EventManager] = None,
        event_managed: typing.Optional[bool] = None,
        server: typing.Optional[hikari.api.InteractionServer] = None,
    ) -> None:
        """Initialise a modal client.

        This registers [ModalClient][yuyo.modals.ModalClient] as a type
        dependency when `alluka` isn't passed.

        !!! note
            For an easier way to initialise the client from a bot see
            [ModalClient.from_gateway_bot][yuyo.modals.ModalClient.from_gateway_bot],
            [ModalClient.from_rest_bot][yuyo.modals.ModalClient.from_rest_bot], and
            [ModalClient.from_tanjun][yuyo.modals.ModalClient.from_tanjun].

        Parameters
        ----------
        alluka
            The Alluka client to use for callback dependency injection in this client.

            If not provided then this will initialise its own Alluka client.
        event_manager
            The event manager this client should listen to dispatched modal
            interactions from if applicable.
        event_managed
            Whether this client should be automatically opened and closed based on
            the lifetime events dispatched by `event_manager`.

            Defaults to [True][] if an event manager is passed.
        server
            The server this client should listen to modal interactions
            from if applicable.

        Raises
        ------
        ValueError
            If `event_managed` is passed as [True][] when `event_manager` is [None][].
        """
        if alluka is None:
            alluka = alluka_.Client()
            self._set_standard_deps(alluka)

        self._alluka = alluka
        self._modals: dict[str, tuple[timeouts.AbstractTimeout, AbstractModal]] = {}
        self._event_manager = event_manager
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._prefix_ids: dict[str, tuple[timeouts.AbstractTimeout, AbstractModal]] = {}
        self._server = server
        self._tasks: list[asyncio.Task[typing.Any]] = []

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

    @classmethod
    def from_gateway_bot(
        cls,
        bot: hikari.EventManagerAware,
        /,
        *,
        alluka: typing.Optional[alluka_.abc.Client] = None,
        event_managed: bool = True,
    ) -> Self:
        """Build a modal client from a Gateway Bot.

        This registers [ModalClient][yuyo.modals.ModalClient] as a type
        dependency when `alluka` isn't passed.

        Parameters
        ----------
        bot
            The Gateway bot this modal client should be bound to.
        alluka
            The Alluka client to use for callback dependency injection in this client.

            If not provided then this will initialise its own Alluka client.
        event_managed
            Whether the modal client should be automatically opened and
            closed based on the lifetime events dispatched by `bot`.

        Returns
        -------
        ModalClient
            The initialised modal client.
        """
        return cls(alluka=alluka, event_manager=bot.event_manager, event_managed=event_managed)

    @classmethod
    def from_rest_bot(
        cls,
        bot: hikari.RESTBotAware,
        /,
        *,
        alluka: typing.Optional[alluka_.abc.Client] = None,
        bot_managed: bool = False,
    ) -> Self:
        """Build a modal client from a REST Bot.

        This registers [ModalClient][yuyo.modals.ModalClient] as a type
        dependency when `alluka` isn't passed.

        Parameters
        ----------
        bot
            The REST bot this modal client should be bound to.
        alluka
            The Alluka client to use for callback dependency injection in this client.

            If not provided then this will initialise its own Alluka client.
        bot_managed
            Whether the modal client should be automatically opened and
            closed based on the Bot's startup and shutdown callbacks.

        Returns
        -------
        ModalClient
            The initialised modal client.
        """
        client = cls(alluka=alluka, server=bot.interaction_server)

        if bot_managed:
            bot.add_startup_callback(client._on_starting)
            bot.add_shutdown_callback(client._on_stopping)

        return client

    @classmethod
    def from_tanjun(cls, tanjun_client: tanjun.abc.Client, /, *, tanjun_managed: bool = True) -> Self:
        """Build a modal client from a Tanjun client.

        This will use the Tanjun client's alluka client and registers
        [ModalClient][yuyo.modals.ModalClient] as a type dependency on Tanjun.

        Parameters
        ----------
        tanjun_client
            The Tanjun client this modal client should be bound to.
        tanjun_managed
            Whether the modal client should be automatically opened and
            closed based on the Tanjun client's lifetime client callback.

        Returns
        -------
        ModalClient
            The initialised modal client.
        """
        import tanjun

        self = cls(alluka=tanjun_client.injector, event_manager=tanjun_client.events, server=tanjun_client.server)
        self._set_standard_deps(tanjun_client.injector)

        if tanjun_managed:
            tanjun_client.add_client_callback(tanjun.ClientCallbackNames.STARTING, self.open)
            tanjun_client.add_client_callback(tanjun.ClientCallbackNames.CLOSING, self.close)

        return self

    def _set_standard_deps(self, alluka: alluka_.abc.Client, /) -> None:
        alluka.set_type_dependency(ModalClient, self)

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
            for custom_id, (timeout, _) in tuple(self._modals.items()):
                if not timeout.has_expired or custom_id not in self._modals:
                    continue

                del self._modals[custom_id]

            for prefix, (timeout, _) in tuple(self._prefix_ids.items()):
                if not timeout.has_expired or prefix not in self._prefix_ids:
                    continue

                del self._prefix_ids[prefix]

            await asyncio.sleep(5)  # TODO: is this a good time?

    def close(self) -> None:
        """Close the modal client."""
        if not self._gc_task:
            return

        self._gc_task.cancel()
        self._gc_task = None
        if self._server:
            self._server.set_listener(hikari.ModalInteraction, None)

        if self._event_manager:
            self._event_manager.unsubscribe(hikari.InteractionCreateEvent, self.on_gateway_event)

        self._modals = {}
        # TODO: have the executors be runnable and close them here?

    def open(self) -> None:
        """Startup the modal client."""
        if self._gc_task:
            return

        self._gc_task = asyncio.get_running_loop().create_task(self._gc())

        if self._server:
            self._server.set_listener(hikari.ModalInteraction, self.on_rest_request)

        if self._event_manager:
            self._event_manager.subscribe(hikari.InteractionCreateEvent, self.on_gateway_event)

    async def _execute_modal(
        self,
        modal: AbstractModal,
        interaction: hikari.ModalInteraction,
        /,
        *,
        future: typing.Optional[asyncio.Future[_ModalResponseT]] = None,
    ) -> None:
        ctx = ModalContext(self, interaction, self._add_task, response_future=future)
        await modal.execute(ctx)

    async def _execute_prefix_modal(
        self,
        modal: AbstractModal,
        interaction: hikari.ModalInteraction,
        /,
        *,
        future: typing.Optional[asyncio.Future[_ModalResponseT]] = None,
    ) -> None:
        ctx = ModalContext(self, interaction, self._add_task, response_future=future)
        await modal.execute(ctx)

    async def on_gateway_event(self, event: hikari.InteractionCreateEvent, /) -> None:
        """Process an interaction create gateway event.

        Parameters
        ----------
        event
            The interaction create gateway event to process.
        """
        if not isinstance(event.interaction, hikari.ModalInteraction):
            return

        if (entry := self._modals.get(event.interaction.custom_id)) and not entry[0].has_expired:
            if entry[0].increment_uses():
                del self._modals[event.interaction.custom_id]

            await self._execute_modal(entry[1], event.interaction)
            return

        prefix = event.interaction.custom_id.split(":", 1)[0]
        if (entry := self._prefix_ids.get(prefix)) and not entry[0].has_expired:
            if entry[0].increment_uses():
                del self._prefix_ids[prefix]

            await self._execute_prefix_modal(entry[1], event.interaction)
            return

        await event.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE, "This modal has timed-out.", flags=hikari.MessageFlag.EPHEMERAL
        )

    async def on_rest_request(self, interaction: hikari.ModalInteraction, /) -> _ModalResponseT:
        """Process a modal interaction REST request.

        Parameters
        ----------
        interaction
            The interaction to process.

        Returns
        -------
        hikari.api.InteractionMessageBuilder | hikari.api.InteractionDeferredBuilder
            The REST re sponse.
        """
        if (entry := self._modals.get(interaction.custom_id)) and not entry[0].has_expired:
            if entry[0].increment_uses():
                del self._modals[interaction.custom_id]

            future = asyncio.Future()
            self._add_task(asyncio.create_task(self._execute_modal(entry[1], interaction, future=future)))
            return await future

        prefix = interaction.custom_id.split(":", 1)[0]
        if (entry := self._prefix_ids.get(prefix)) and not entry[0].has_expired:
            if entry[0].increment_uses():
                del self._prefix_ids[prefix]

            future: asyncio.Future[_ModalResponseT] = asyncio.Future()
            self._add_task(asyncio.create_task(self._execute_prefix_modal(entry[1], interaction, future=future)))
            return await future

        return (
            interaction.build_response()
            .set_content("This modal has timed-out.")
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    def set_modal(
        self,
        custom_id: str,
        modal: AbstractModal,
        /,
        *,
        prefix_match: bool = False,
        timeout: typing.Union[timeouts.AbstractTimeout, None, NoDefault] = NO_DEFAULT,
    ) -> Self:
        """Register a modal for a custom ID.

        Parameters
        ----------
        custom_id
            The custom_id to register the modal for.
        modal
            The modal to register.
        prefix_match
            Whether `custom_id` should be matched as a prefix.

            When this is [True][] `custom_id` will be matched against
            `.split(":", 1)[0]`.

            This allows for further state to be held in the custom ID after the
            prefix and is lower priority than normal matching.
        timeout
            Timeout strategy for this modal.

            Passing [None][] here will set [NeverTimeout][yuyo.timeouts.NeverTimeout].

        Returns
        -------
        Self
            The modal client to allow chaining.

        Raises
        ------
        ValueError
            If the custom_id is already registered.
        """
        if custom_id in self._prefix_ids:
            raise ValueError(f"{custom_id!r} is already registered as a prefix match")

        if custom_id in self._modals:
            raise ValueError(f"{custom_id!r} is already registered as a normal match")

        if timeout is NO_DEFAULT:
            timeout = timeouts.BasicTimeout(datetime.timedelta(minutes=2))

        elif timeout is None:
            timeout = timeouts.NeverTimeout()

        if prefix_match:
            self._prefix_ids[custom_id] = (timeout, modal)
            return self

        self._modals[custom_id] = (timeout, modal)
        return self

    def get_modal(self, custom_id: str, /) -> typing.Optional[AbstractModal]:
        """Get the modal set for a custom ID.

        Parameters
        ----------
        custom_id
            The custom_id to get the modal for.

        Returns
        -------
        AbstractModal | None
            The callback for the custom_id, or [None][] if it doesn't exist.
        """
        if entry := self._modals.get(custom_id) or self._prefix_ids.get(custom_id):
            return entry[1]

        return None

    def remove_modal(self, custom_id: str, /) -> Self:
        """Remove the modal set for a custom ID.

        Parameters
        ----------
        custom_id
            The custom_id to unset the modal for.

        Returns
        -------
        Self
            The modal client to allow chaining.

        Raises
        ------
        KeyError
            If the custom_id is not registered.
        """
        try:
            del self._modals[custom_id]
        except KeyError:
            del self._prefix_ids[custom_id]

        return self


Client = ModalClient
"""Alias of [ModalClient][yuyo.modals.ModalClient]."""


class AbstractModal(abc.ABC):
    """Base class for a modal execution handler."""

    __slots__ = ()

    @abc.abstractmethod
    async def execute(self, ctx: ModalContext, /) -> None:
        """Execute this modal.

        Parameters
        ----------
        ctx
            The context to execute this with.
        """


class _TrackedField:
    __slots__ = ("custom_id", "default", "parameter", "prefix_match", "type")

    def __init__(
        self,
        *,
        custom_id: str,
        default: typing.Union[typing.Any, NoDefault],
        parameter: str,
        prefix_match: bool,
        type_: hikari.ComponentType,
    ) -> None:
        self.custom_id = custom_id
        self.default = default
        self.parameter = parameter
        self.prefix_match = prefix_match
        self.type = type_

    def process(
        self,
        compiled_prefixes: dict[str, hikari.ModalComponentTypesT],
        components: dict[str, hikari.ModalComponentTypesT],
        /,
    ) -> typing.Any:
        if self.prefix_match:
            component = compiled_prefixes.get(self.custom_id)

        else:
            component = components.get(self.custom_id)

        # Discord still provides text components when no input was given just with
        # an empty string for `value` but we also want to support possible future
        # cases where they just just don't provide the component.
        if not component or not component.value:
            if self.default is NO_DEFAULT:
                raise RuntimeError(f"Missing required component `{self.custom_id}`")

            return self.default

        if component.type is not self.type:
            raise RuntimeError(
                f"Mismatched component type, expected {self.type} for `{self.custom_id}` but got {component.type}"
            )

        return component.value


class _TrackedDataclass:
    __slots__ = ("_dataclass", "_fields", "parameter")

    def __init__(self, keyword: str, dataclass: type[ModalOptions], fields: list[_TrackedField], /) -> None:
        self._dataclass = dataclass
        self._fields = fields
        self.parameter = keyword

    def process(
        self,
        compiled_prefixes: dict[str, hikari.ModalComponentTypesT],
        components: dict[str, hikari.ModalComponentTypesT],
    ) -> typing.Any:
        sub_fields = {field.parameter: field.process(compiled_prefixes, components) for field in self._fields}
        return self._dataclass(**sub_fields)


class Modal(AbstractModal):
    """Standard implementation of a modal executor.

    To send this modal pass [Modal.rows][yuyo.modals.Modal.rows] as `components`
    when calling `create_modal_response`.

    Examples
    --------

    There's a few different ways this can be used to create a modal.

    Sub-components can be added to an instance of a modal using chainable
    methods:

    ```py
    async def callback(
        ctx: modals.ModalContext, field: str, other_field: str | None
    ) -> None:
        await ctx.respond("hi")

    modal = (
        modals.modal(callback, ephemeral_default=True)
        .add_text_input("Title A", parameter="field")
        .add_text_input(
            "Title B",
            style=hikari.TextInputStyle.PARAGRAPH,
            parameter="other_field",
            default=None,
        )
    )
    ```

    or using decorator methods:

    ```py
    @modals.with_text_input(
        "Title B",
        style=hikari.TextInputStyle.PARAGRAPH,
        parameter="other_field",
        default=None,
    )
    @modals.with_text_input("Title A", parameter="field")
    @modals.as_modal(ephemeral_default=True)
    async def callback(
        ctx: modals.ModalContext, field: str, other_field: str | None
    ) -> None:
        await ctx.respond("bye")
    ```

    !!! note
        Since decorators are executed from the bottom upwards fields added
        through decorator calls will follow the same order.

    Subclasses of [Modal][yuyo.modals.Modal] can act as a template where
    "static" fields are included on all instances and subclasses of that class:

    ```py
    @modals.with_static_text_input(
        "Title B",
        style=hikari.TextInputStyle.PARAGRAPH,
        parameter="other_field",
        default=None,
    )
    @modals.with_static_text_input("Title A", parameter="field")
    class CustomModal(modals.Modal):
        # The init can be overridden to store extra data on the column object when subclassing.
        def __init__(self, special_string: str, ephemeral_default: bool = False):
            super().__init__(ephemeral_default=ephemeral_default)
            self.special_string = special_string

        async def callback(
            ctx: modals.ModalContext,
            field: str,
            other_field: str | None,
            value: str
        ) -> None:
            await ctx.respond("Good job")
    ```

    Templates can be made by subclassing [Modal][yuyo.modals.Modal] and
    defining the method `callback` for handling context  menu execution
    (this must be valid for the signature signature
    `(modals.ModalContext, ...) -> Coroutine[Any, Any, None]`).

    ```py
    @modals.with_static_text_input(
        "Title B",
        style=hikari.TextInputStyle.PARAGRAPH,
        parameter="other_field",
        default=None,
    )
    @modals.with_static_text_input("Title A", parameter="field")
    @modals.as_modal_template
    async def custom_modal(
        ctx: modals.ModalContext,
        field: str,
        other_field: str | None,
        value: str,
    ) -> None:
        await ctx.respond("Bye")
    ```

    or by using [as_modal_template][yuyo.modals.as_modal_template] (which returns
    a class which functions like a [Modal][yuyo.modals.Modal] subclass) The
    chainable `add_static_{}()` classmethods can also be used to add static fields
    to a [Modal][yuyo.modals.Modal] subclass.

    Modals also support declaring entries using the following parameter descriptors:

    * [text_input][yuyo.modals.text_input]

    ```py
    class ModalOptions(modals.ModalOptions):
        foo: str = modals.text_input("label")
        bar: str | None = modals.text_unput(
            "label", style=hikari.TextInputStyle.PARAGRAPH, default=None
        )

    @yuyo.modals.as_modal_template
    async def callback(
        ctx: modals.ModalContext,
        options: ModalOptions,
        field: str = modals.text_input("label", value="yeet")
    )
    ```

    These can either be applied to the default of an argument or defined as an
    attribute on a [ModalOptions][yuyo.modals.ModalOptions] subclass (
    `ModalOptions` should then be used as an argument's type-hint). This also
    works for [Modal][yuyo.modals.Modal] subclasses which have a
    `Modal.callback` method.
    """

    __slots__ = ("_ephemeral_default", "_rows", "_tracked_fields")

    _static_fields: typing.ClassVar[list[_TrackedField | _TrackedDataclass]] = []
    _static_rows: typing.ClassVar[list[hikari.impl.ModalActionRowBuilder]] = []

    def __init__(self, *, ephemeral_default: bool = False) -> None:
        """Initialise a component executor.

        Parameters
        ----------
        ephemeral_default
            Whether this executor's responses should default to being ephemeral.
        """
        self._ephemeral_default = ephemeral_default
        self._rows: list[hikari.impl.ModalActionRowBuilder] = self._static_rows.copy()
        # TODO: don't duplicate fields when re-declared
        self._tracked_fields: list[_TrackedField | _TrackedDataclass] = self._static_fields.copy()

    def __init_subclass__(cls, parse_signature: bool = True) -> None:
        cls._static_fields = []
        cls._static_rows = []

        if not parse_signature:
            return

        try:
            cls.callback

        except AttributeError:
            pass

        else:
            for name, descriptor in _parse_descriptors(cls.callback):
                descriptor.add_static(name, cls)

    callback: typing.ClassVar[collections.abc.Callable[_SelfishSig[Self], _CoroT[None]]]

    @property
    def rows(self) -> collections.abc.Sequence[hikari.api.ModalActionRowBuilder]:
        """Builder objects of the rows in this modal."""
        return self._rows

    @classmethod
    def add_static_dataclass(cls, options: type[ModalOptions], /, *, keyword: str | None = None) -> type[Self]:
        if keyword:
            fields: list[_TrackedField] = []

            for name, descriptor in options._modal_fields.items():  # pyright: ignore [ reportPrivateUsage ]
                descriptor.add_static(None, cls)
                fields.append(descriptor.to_tracked_field(name))

            cls._static_fields.append(_TrackedDataclass(keyword, options, fields))

        else:
            for name, descriptor in options._modal_fields.items():  # pyright: ignore [ reportPrivateUsage ]
                descriptor.add_static(None, cls)

        return cls

    def add_dataclass(self, options: type[ModalOptions], /, *, keyword: str | None = None) -> Self:
        if keyword:
            fields: list[_TrackedField] = []

            for name, descriptor in options._modal_fields.items():  # pyright: ignore [ reportPrivateUsage ]
                descriptor.add(None, self)
                fields.append(descriptor.to_tracked_field(name))

            self._static_fields.append(_TrackedDataclass(keyword, options, fields))

        else:
            for name, descriptor in options._modal_fields.items():  # pyright: ignore [ reportPrivateUsage ]
                descriptor.add(None, self)

        return self

    @classmethod
    def add_static_text_input(
        cls,
        label: str,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        style: hikari.TextInputStyle = hikari.TextInputStyle.SHORT,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        value: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        default: typing.Union[typing.Any, NoDefault] = NO_DEFAULT,
        min_length: int = 0,
        max_length: int = 4000,
        prefix_match: bool = False,
        parameter: typing.Optional[str] = None,
    ) -> type[Self]:
        """Add a text input field to all instances and subclasses of this modal class.

        Parameters
        ----------
        label
            The text input field's display label.

            This cannot be greater than 45 characters long.
        custom_id
            The field's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.
        style
            The text input's style.
        placeholder
            Placeholder text to display when the text input is empty.
        value
            Default text to pre-fill the field with.
        default
            Default value to pass if this text input field was not provided.

            The field will be marked as required unless this is supplied.

            This will also be used for `value` when it has been left undefined
            and the default is a string that's <=4000 characters in length.
        min_length
            Minimum length the input text can be.

            This can be greater than or equal to 0 and less than or equal to 4000.
        max_length
            Maximum length the input text can be.

            This can be greater than or equal to 1 and less than or equal to 4000.
        prefix_match
            Whether `custom_id` should be matched as a prefix.

            When this is [True][] `custom_id` will be matched against
            `.split(":", 1)[0]`.

            This allows for further state to be held in the custom ID after the
            prefix and is lower priority than normal matching.
        parameter
            Name of the parameter the text for this field should be passed to.

            This will be of type [str][] and may also be the value passed for
            `default`.

        Returns
        -------
        type[Self]
            The class to enable call chaining.

        Raises
        ------
        RuntimeError
            When called directly on [modals.Modal][yuyo.modals.Modal]
            (rather than on a subclass).
        """
        if cls is Modal:
            raise RuntimeError("Can only add static fields to subclasses")

        custom_id, row = _make_text_input(
            custom_id=custom_id,
            label=label,
            style=style,
            placeholder=placeholder,
            value=_workout_value(default, value),
            default=default,
            min_length=min_length,
            max_length=max_length,
        )
        cls._static_rows.append(row)

        if parameter:
            field = _TrackedField(
                custom_id=custom_id,
                default=default,
                parameter=parameter,
                prefix_match=prefix_match,
                type_=hikari.ComponentType.TEXT_INPUT,
            )
            cls._static_fields.append(field)

        return cls

    def add_text_input(
        self,
        label: str,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        style: hikari.TextInputStyle = hikari.TextInputStyle.SHORT,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        value: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        default: typing.Union[typing.Any, NoDefault] = NO_DEFAULT,
        min_length: int = 0,
        max_length: int = 4000,
        prefix_match: bool = False,
        parameter: typing.Optional[str] = None,
    ) -> Self:
        """Add a text input field to this modal instance.

        Parameters
        ----------
        label
            The text input field's display label.

            This cannot be greater than 45 characters long.
        custom_id
            The field's custom ID.

            Defaults to a UUID and cannot be longer than 100 characters.
        style
            The text input's style.
        placeholder
            Placeholder text to display when the text input is empty.
        value
            Default text to pre-fill the field with.
        default
            Default value to pass if this text input field was not provided.

            The field will be marked as required unless this is supplied.

            This will also be used for `value` when it has been left undefined
            and the default is a string that's <=4000 characters in length.
        min_length
            Minimum length the input text can be.

            This can be greater than or equal to 0 and less than or equal to 4000.
        max_length
            Maximum length the input text can be.

            This can be greater than or equal to 1 and less than or equal to 4000.
        prefix_match
            Whether `custom_id` should be matched as a prefix.

            When this is [True][] `custom_id` will be matched against
            `.split(":", 1)[0]`.

            This allows for further state to be held in the custom ID after the
            prefix and is lower priority than normal matching.
        parameter
            Name of the parameter the text for this field should be passed to.

            This will be of type [str][] and may also be the value passed for
            `default`.

        Returns
        -------
        Self
            The model instance to enable call chaining.
        """
        custom_id, row = _make_text_input(
            custom_id=custom_id,
            label=label,
            style=style,
            placeholder=placeholder,
            value=_workout_value(default, value),
            default=default,
            min_length=min_length,
            max_length=max_length,
        )
        self._rows.append(row)

        if parameter:
            self._tracked_fields.append(
                _TrackedField(
                    custom_id=custom_id,
                    default=default,
                    parameter=parameter,
                    prefix_match=prefix_match,
                    type_=hikari.ComponentType.TEXT_INPUT,
                )
            )

        return self

    async def execute(self, ctx: ModalContext, /) -> None:
        # <<inherited docstring from AbstractModal>>.
        ctx.set_ephemeral_default(self._ephemeral_default)
        compiled_prefixes: dict[str, hikari.ModalComponentTypesT] = {}
        components: dict[str, hikari.ModalComponentTypesT] = {}

        component: typing.Optional[hikari.ModalComponentTypesT]  # MyPy compat
        for component in itertools.chain.from_iterable(
            component_.components for component_ in ctx.interaction.components
        ):
            components[component.custom_id] = component
            compiled_prefixes[component.custom_id.split(":", 1)[0]] = component

        fields = {field.parameter: field.process(compiled_prefixes, components) for field in self._tracked_fields}
        await ctx.client.alluka.call_with_async_di(self.callback, ctx, **fields)


def _workout_value(default: typing.Any, value: hikari.UndefinedOr[str]) -> hikari.UndefinedOr[str]:
    if value is not hikari.UNDEFINED or default is hikari.UNDEFINED:
        return value

    if isinstance(default, str) and len(default) <= 4000:
        return default

    return value


def _make_text_input(
    *,
    label: str,
    custom_id: typing.Optional[str],
    style: hikari.TextInputStyle,
    placeholder: hikari.UndefinedOr[str],
    value: hikari.UndefinedOr[str],
    default: typing.Union[typing.Any, NoDefault],
    min_length: int,
    max_length: int,
) -> tuple[str, hikari.impl.ModalActionRowBuilder]:
    if custom_id is None:
        custom_id = _internal.random_custom_id()

    # TODO: TextInputBuilder is inconsistent.
    component = hikari.impl.TextInputBuilder(
        container=NotImplemented,
        label=label,
        custom_id=custom_id,
        style=style,
        placeholder=placeholder,
        value=value,
        required=default is NO_DEFAULT,
        min_length=min_length,
        max_length=max_length,
    )
    row = hikari.impl.ModalActionRowBuilder(components=[component])
    return (custom_id, row)


class _DynamicModal(Modal, typing.Generic[_P], parse_signature=False):
    __slots__ = ("_callback",)

    def __init__(
        self, callback: collections.abc.Callable[_P, _CoroT[None]], /, *, ephemeral_default: bool = False
    ) -> None:
        super().__init__(ephemeral_default=ephemeral_default)
        self._callback = callback

    def callback(self, *args: _P.args, **kwargs: _P.kwargs) -> _CoroT[None]:
        return self._callback(*args, **kwargs)


def modal(
    callback: collections.abc.Callable[_P, _CoroT[None]],
    /,
    *,
    ephemeral_default: bool = False,
    parse_signature: bool = False,
) -> _DynamicModal[_P]:
    """Create a modal instance for a callback.

    !!! info
        This won't parse the callback for parameter descriptors and
        [ModalOptions][yuyo.modals.ModalOptions] unless `parse_signature=True`
        is passed, unlike [as_modal_template][yuyo.modals.as_modal_template]
        and [Modal][yuyo.modals.Modal] subclasses.

    Parameters
    ----------
    callback
        Callback to use for modal execution.
    ephemeral_default
        Whether this modal's responses should default to ephemeral.
    parse_signature
        Whether to parse the signature for parameter descriptors and
        [ModalOptions][yuyo.modals.ModalOptions] type-hints.

    Returns
    -------
    Modal
        The created modal.
    """
    modal = _DynamicModal(callback, ephemeral_default=ephemeral_default)
    if parse_signature:
        for name, descriptor in _parse_descriptors(callback):
            descriptor.add(name, modal)

    return modal


@typing.overload
def as_modal(callback: collections.abc.Callable[_P, _CoroT[None]], /) -> _DynamicModal[_P]:
    ...


@typing.overload
def as_modal(
    *, ephemeral_default: bool = False
) -> collections.abc.Callable[[collections.abc.Callable[_P, _CoroT[None]]], _DynamicModal[_P]]:
    ...


def as_modal(
    callback: typing.Optional[collections.abc.Callable[_P, _CoroT[None]]] = None,
    /,
    *,
    ephemeral_default: bool = False,
    parse_signature: bool = False,
) -> typing.Union[
    _DynamicModal[_P], collections.abc.Callable[[collections.abc.Callable[_P, _CoroT[None]]], _DynamicModal[_P]]
]:
    """Create a modal instance through a decorator call.

    !!! info
        This won't parse the callback for parameter descriptors and
        [ModalOptions][yuyo.modals.ModalOptions] unless `parse_signature=True`
        is passed, unlike [as_modal_template][yuyo.modals.as_modal_template]
        and [Modal][yuyo.modals.Modal] subclasses.

    Parameters
    ----------
    ephemeral_default
        Whether this modal's responses should default to ephemeral.
    parse_signature
        Whether to parse the signature for parameter descriptors and
        [ModalOptions][yuyo.modals.ModalOptions] type-hints.

    Returns
    -------
    Modal
        The new decorated modal.
    """

    def decorator(callback: collections.abc.Callable[_P, _CoroT[None]], /) -> _DynamicModal[_P]:
        return modal(callback, ephemeral_default=ephemeral_default, parse_signature=parse_signature)

    if callback:
        return decorator(callback)

    return decorator


# Putting typing.Generic after Modal here breaks Python's generic handling.
class _GenericModal(typing.Generic[_P], Modal, parse_signature=False):
    __slots__ = ()

    async def callback(self, *arg: _P.args, **kwargs: _P.kwargs) -> None:
        raise NotImplementedError


@typing.overload
def as_modal_template(callback: collections.abc.Callable[_P, _CoroT[None]], /) -> type[_GenericModal[_P]]:
    ...


@typing.overload
def as_modal_template(
    *, ephemeral_default: bool = False
) -> collections.abc.Callable[[collections.abc.Callable[_P, _CoroT[None]]], type[_GenericModal[_P]]]:
    ...


def as_modal_template(
    callback: typing.Optional[collections.abc.Callable[_P, _CoroT[None]]] = None,
    /,
    *,
    ephemeral_default: bool = False,
    parse_signature: bool = True,
) -> typing.Union[
    type[_GenericModal[_P]],
    collections.abc.Callable[[collections.abc.Callable[_P, _CoroT[None]]], type[_GenericModal[_P]]],
]:
    """Create a modal template through a decorator callback.

    This supports the same decorators and parameter descriptors for declaring
    the modal's entries as a normal modal class.

    Parameters
    ----------
    ephemeral_default
        Whether this modal's responses should default to ephemeral.
    parse_signature
        Whether to parse the signature for parameter descriptors and
        [ModalOptions][yuyo.modals.ModalOptions] type-hints.

    Returns
    -------
    type[Modal]
        The new decorated modal class.
    """

    def decorator(callback_: collections.abc.Callable[_P, _CoroT[None]], /) -> type[_GenericModal[_P]]:
        class ModalTemplate(_GenericModal[_P], parse_signature=parse_signature):
            __slots__ = ()

            def __init__(self, *, ephemeral_default: bool = ephemeral_default) -> None:
                super().__init__(ephemeral_default=ephemeral_default)

            @functools.wraps(callback_)
            def callback(self, *args: _P.args, **kwargs: _P.kwargs) -> _CoroT[None]:
                return callback_(*args, **kwargs)

        return ModalTemplate

    if callback:
        return decorator(callback)

    return decorator


def with_static_text_input(
    label: str,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    style: hikari.TextInputStyle = hikari.TextInputStyle.SHORT,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    value: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    default: typing.Union[typing.Any, NoDefault] = NO_DEFAULT,
    min_length: int = 0,
    max_length: int = 4000,
    prefix_match: bool = False,
    parameter: typing.Optional[str] = None,
) -> collections.abc.Callable[[type[_ModalT]], type[_ModalT]]:
    """Add a static text input field to the decorated modal subclass.

    Parameters
    ----------
    label
        The text input field's display label.

        This cannot be greater than 45 characters long.
    custom_id
        The field's custom ID.

        Defaults to a UUID and cannot be longer than 100 characters.
    style
        The text input's style.
    placeholder
        Placeholder text to display when the text input is empty.
    value
        Default text to pre-fill the field with.
    default
        Default value to pass if this text input field was not provided.

        The field will be marked as required unless this is supplied.

        This will also be used for `value` when it has been left undefined
        and the default is a string that's <=4000 characters in length.
    min_length
        Minimum length the input text can be.

        This can be greater than or equal to 0 and less than or equal to 4000.
    max_length
        Maximum length the input text can be.

        This can be greater than or equal to 1 and less than or equal to 4000.
    prefix_match
        Whether `custom_id` should be matched as a prefix.

        When this is [True][] `custom_id` will be matched against
        `.split(":", 1)[0]`.

        This allows for further state to be held in the custom ID after the
        prefix and is lower priority than normal matching.
    parameter
        Name of the parameter the text for this field should be passed to.

        This will be of type [str][] and may also be the value passed for
        `default`.

    Returns
    -------
    type[Modal]
        The decorated modal class.
    """
    return lambda modal_cls: modal_cls.add_static_text_input(
        label,
        custom_id=custom_id,
        style=style,
        placeholder=placeholder,
        value=value,
        default=default,
        min_length=min_length,
        max_length=max_length,
        prefix_match=prefix_match,
        parameter=parameter,
    )


def with_text_input(
    label: str,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    style: hikari.TextInputStyle = hikari.TextInputStyle.SHORT,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    value: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    default: typing.Union[typing.Any, NoDefault] = NO_DEFAULT,
    min_length: int = 0,
    max_length: int = 4000,
    prefix_match: bool = False,
    parameter: typing.Optional[str] = None,
) -> collections.abc.Callable[[_ModalT], _ModalT]:
    """Add a text input field to the decorated modal instance.

    Parameters
    ----------
    label
        The text input field's display label.

        This cannot be greater than 45 characters long.
    custom_id
        The field's custom ID.

        Defaults to a UUID and cannot be longer than 100 characters.
    style
        The text input's style.
    placeholder
        Placeholder text to display when the text input is empty.
    value
        Default text to pre-fill the field with.
    default
        Default value to pass if this text input field was not provided.

        The field will be marked as required unless this is supplied.

        This will also be used for `value` when it has been left undefined
        and the default is a string that's <=4000 characters in length.
    min_length
        Minimum length the input text can be.

        This can be greater than or equal to 0 and less than or equal to 4000.
    max_length
        Maximum length the input text can be.

        This can be greater than or equal to 1 and less than or equal to 4000.
    prefix_match
        Whether `custom_id` should be matched as a prefix.

        When this is [True][] `custom_id` will be matched against
        `.split(":", 1)[0]`.

        This allows for further state to be held in the custom ID after the
        prefix and is lower priority than normal matching.
    parameter
        Name of the parameter the text for this field should be passed to.

        This will be of type [str][] and may also be the value passed for
        `default`.

    Returns
    -------
    Modal
        The decorated modal instance.
    """
    return lambda modal: modal.add_text_input(
        label,
        custom_id=custom_id,
        style=style,
        placeholder=placeholder,
        value=value,
        default=default,
        min_length=min_length,
        max_length=max_length,
        prefix_match=prefix_match,
        parameter=parameter,
    )


def _parse_descriptors(
    callback: collections.abc.Callable[..., typing.Any], /
) -> collections.abc.Iterable[tuple[str, _ComponentDescriptor]]:
    for name, parameter in inspect.signature(callback, eval_str=True).parameters.items():
        if parameter.default is not parameter.empty and isinstance(parameter.default, _ComponentDescriptor):
            yield name, parameter.default

        elif parameter.annotation is parameter.empty:
            continue

        if isinstance(parameter.annotation, type) and issubclass(parameter.annotation, ModalOptions):
            yield name, _ModalOptionsDescriptor(parameter.annotation)


class _ComponentDescriptor(abc.ABC):
    __slots__ = ()

    @abc.abstractmethod
    def add(self, keyword: str | None, modal: Modal, /) -> None:
        ...

    @abc.abstractmethod
    def add_static(self, keyword: str | None, modal: type[Modal], /) -> None:
        ...

    @abc.abstractmethod
    def to_tracked_field(self, keyword: str, /) -> _TrackedField:
        ...


class _ModalOptionsDescriptor(_ComponentDescriptor):
    __slots__ = ("_options",)

    def __init__(self, options: type[ModalOptions], /) -> None:
        self._options = options

    def add(self, keyword: str | None, modal: Modal, /) -> None:
        modal.add_dataclass(self._options, keyword=keyword)

    def add_static(self, keyword: str | None, modal: type[Modal], /) -> None:
        modal.add_static_dataclass(self._options, keyword=keyword)

    def to_tracked_field(self, keyword: str, /) -> _TrackedField:
        raise NotImplementedError


class _TextInputDescriptor(_ComponentDescriptor):
    __slots__ = (
        "_label",
        "_custom_id",
        "_style",
        "_placeholder",
        "_value",
        "_default",
        "_min_length",
        "_max_length",
        "_prefix_match",
    )

    def __init__(
        self,
        label: str,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        style: hikari.TextInputStyle = hikari.TextInputStyle.SHORT,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        value: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        default: typing.Union[typing.Any, NoDefault] = NO_DEFAULT,
        min_length: int = 0,
        max_length: int = 4000,
        prefix_match: bool = False,
    ) -> None:
        self._label = label
        self._custom_id = custom_id or _internal.random_custom_id()
        self._style = style
        self._placeholder = placeholder
        self._value = value
        self._default = default
        self._min_length = min_length
        self._max_length = max_length
        self._prefix_match = prefix_match

    def add(self, keyword: str | None, modal: Modal, /) -> None:
        modal.add_text_input(
            self._label,
            parameter=keyword,
            custom_id=self._custom_id,
            style=self._style,
            placeholder=self._placeholder,
            value=self._value,
            default=self._default,
            min_length=self._min_length,
            max_length=self._max_length,
            prefix_match=self._prefix_match,
        )

    def add_static(self, keyword: str | None, modal: type[Modal], /) -> None:
        modal.add_static_text_input(
            self._label,
            parameter=keyword,
            custom_id=self._custom_id,
            style=self._style,
            placeholder=self._placeholder,
            value=self._value,
            default=self._default,
            min_length=self._min_length,
            max_length=self._max_length,
            prefix_match=self._prefix_match,
        )

    def to_tracked_field(self, keyword: str, /) -> _TrackedField:
        return _TrackedField(
            custom_id=self._custom_id,
            default=self._default,
            parameter=keyword,
            prefix_match=self._prefix_match,
            type_=hikari.ComponentType.TEXT_INPUT,
        )


@typing.overload
def text_input(
    label: str,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    style: hikari.TextInputStyle = hikari.TextInputStyle.SHORT,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    value: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    default: NoDefault = NO_DEFAULT,
    min_length: int = 0,
    max_length: int = 4000,
    prefix_match: bool = False,
) -> str:
    ...


@typing.overload
def text_input(
    label: str,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    style: hikari.TextInputStyle = hikari.TextInputStyle.SHORT,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    value: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    default: _T,
    min_length: int = 0,
    max_length: int = 4000,
    prefix_match: bool = False,
) -> typing.Union[str, _T]:
    ...


def text_input(
    label: str,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    style: hikari.TextInputStyle = hikari.TextInputStyle.SHORT,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    value: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    default: typing.Union[_T, NoDefault] = NO_DEFAULT,
    min_length: int = 0,
    max_length: int = 4000,
    prefix_match: bool = False,
) -> typing.Union[str, _T]:
    """Descriptor used to declare a text input field.

    Parameters
    ----------
    label
        The text input field's display label.

        This cannot be greater than 45 characters long.
    custom_id
        The field's custom ID.

        Defaults to a UUID and cannot be longer than 100 characters.
    style
        The text input's style.
    placeholder
        Placeholder text to display when the text input is empty.
    value
        Default text to pre-fill the field with.
    default
        Default value to pass if this text input field was not provided.

        The field will be marked as required unless this is supplied.

        This will also be used for `value` when it has been left undefined
        and the default is a string that's <=4000 characters in length.
    min_length
        Minimum length the input text can be.

        This can be greater than or equal to 0 and less than or equal to 4000.
    max_length
        Maximum length the input text can be.

        This can be greater than or equal to 1 and less than or equal to 4000.
    prefix_match
        Whether `custom_id` should be matched as a prefix.

        When this is [True][] `custom_id` will be matched against
        `.split(":", 1)[0]`.

        This allows for further state to be held in the custom ID after the
        prefix and is lower priority than normal matching.

    Examples
    --------
    This can either be applied to an argument's default

    ```py
    @modals.as_modal_template
    async def modal_template(
        ctx: modals.ModalContext,
        text_field: str = modals.text_input("label"),
        optional_field: str | None = modals.text_input("label", default=None)
    ) -> None:
        ...
    ```

    Or as an attribute to a [ModalOptions][yuyo.modals.ModalOptions] dataclass.

    ```py
    class ModalOptions(modals.ModalOptions):
        field: str = modals.text_input("label")
        optional_field: str | None = modals.text_input("label", default=None)

    @modals.as_modal_template
    async def modal_template(
        ctx: modals.ModalContext, fields: ModalOptions,
    ) -> None:
        ...
    ```

    """
    descriptor = _TextInputDescriptor(
        label,
        custom_id=custom_id,
        style=style,
        placeholder=placeholder,
        value=value,
        default=default,
        min_length=min_length,
        max_length=max_length,
        prefix_match=prefix_match,
    )
    return typing.cast("str", descriptor)


@typing_extensions.dataclass_transform(field_specifiers=(text_input,), kw_only_default=True, order_default=True)
class _ModalOptionsMeta(type):
    def __new__(
        cls, name: str, bases: tuple[type[typing.Any], ...], namespace: dict[str, typing.Any]
    ) -> _ModalOptionsMeta:
        bases = types.resolve_bases(bases)
        fields: dict[str, _ComponentDescriptor] = {}

        for sub_cls in bases:
            if issubclass(sub_cls, ModalOptions):
                fields.update(sub_cls._modal_fields)  # pyright: ignore [ reportPrivateUsage ]

        for key, value in namespace.items():
            if isinstance(value, _ComponentDescriptor):
                fields[key] = value

        namespace["_modal_fields"] = types.MappingProxyType(fields)
        namedtuple = collections.namedtuple(name, fields.keys())  # pyright: ignore [ reportUntypedNamedTuple ]
        return super().__new__(cls, name, (namedtuple, *bases), namespace)


class ModalOptions(metaclass=_ModalOptionsMeta):
    """Data class used to define a modal's options.

    Examples
    --------
    ```py
    class ModalOptions(modals.ModalOptions):
        field: str = modals.text_input("label")
        optional_field: str | None = modals.text_input("label", default=None)

    @modals.as_modal_template
    async def modal_template(
        ctx: modals.ModalContext, fields: ModalOptions,
    ) -> None:
        ...
    ```
    """

    _modal_fields: typing.ClassVar[types.MappingProxyType[str, _ComponentDescriptor]]
