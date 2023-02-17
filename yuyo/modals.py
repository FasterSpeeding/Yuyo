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
"""Higher level client for callback based modal execution."""
from __future__ import annotations

__all__ = ["ModalClient", "ModalContext", "NO_DEFAULT", "NoDefault"]

import abc
import asyncio
import datetime
import enum
import itertools
import logging
import typing
from collections import abc as collections

import alluka as alluka_
import hikari

from . import _internal
from . import components

if typing.TYPE_CHECKING:
    import types

    from typing_extensions import Self


CallbackSig = collections.Callable[..., collections.Coroutine[typing.Any, typing.Any, None]]
"""Type hint of a modal callback."""

_CallbackSigT = typing.TypeVar("_CallbackSigT", bound=CallbackSig)


ModalResponseT = typing.Union[hikari.api.InteractionMessageBuilder, hikari.api.InteractionDeferredBuilder]
"""Type hint of the builder response types allows for modal interactions."""

_LOGGER = logging.getLogger("hikari.yuyo.modals")


class _NoDefaultEnum(enum.Enum):
    VALUE = object()


NO_DEFAULT = _NoDefaultEnum.VALUE
"""Singleton used to signify when a field has no default."""

NoDefault = typing.Literal[_NoDefaultEnum.VALUE]
"""Type of [yuyo.modals.NO_DEFAULT][]."""


class ModalContext(components.BaseContext[hikari.ModalInteraction]):
    """The context used for modal triggers."""

    __slots__ = ("_client",)

    def __init__(
        self,
        client: ModalClient,
        interaction: hikari.ModalInteraction,
        register_task: collections.Callable[[asyncio.Task[typing.Any]], None],
        *,
        ephemeral_default: bool = False,
        response_future: typing.Optional[asyncio.Future[ModalResponseT]] = None,
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
        attachments: hikari.UndefinedOr[collections.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[collections.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[collections.Sequence[hikari.Embed]] = hikari.UNDEFINED,
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


class ModalClient:
    """Client used to handle modals within a REST or gateway flow."""

    __slots__ = (
        "_alluka",
        "_constant_ids",
        "_event_manager",
        "_gc_task",
        "_modals",
        "_prefix_ids",
        "_server",
        "_tasks",
    )

    def __init__(
        self,
        *,
        alluka: typing.Optional[alluka_.abc.Client] = None,
        event_manager: typing.Optional[hikari.api.EventManager] = None,
        event_managed: typing.Optional[bool] = None,
        server: typing.Optional[hikari.api.InteractionServer] = None,
    ) -> None:
        """Initialise a modal client.

        !!! note
            For an easier way to initialise the client from a bot see
            [yuyo.modals.ModalClient.from_gateway_bot][] and
            [yuyo.modals.ModalClient.from_rest_bot][].

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
        self._alluka = alluka or alluka_.Client()
        self._constant_ids: dict[str, AbstractModal] = {}
        self._event_manager = event_manager
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._modals: dict[str, AbstractModal] = {}
        self._prefix_ids: dict[str, AbstractModal] = {}
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
    def from_gateway_bot(cls, bot: hikari.EventManagerAware, /, *, event_managed: bool = True) -> Self:
        """Build a modal client froma Gateway Bot.

        Parameters
        ----------
        bot
            The Gateway bot this modal client should be bound to.
        event_managed
            Whether the modal client should be automatically opened and
            closed based on the lifetime events dispatched by `bot`.

        Returns
        -------
        ModalClient
            The initialised modal client.
        """
        return cls(event_manager=bot.event_manager, event_managed=event_managed)

    @classmethod
    def from_rest_bot(cls, bot: hikari.InteractionServerAware, /) -> Self:
        """Build a modal client froma REST Bot.

        Parameters
        ----------
        bot
            The REST bot this modal client should be bound to.

        Returns
        -------
        ModalClient
            The initialised modal client.
        """
        return cls(server=bot.interaction_server)

    def _remove_task(self, task: asyncio.Task[typing.Any], /) -> None:
        self._tasks.remove(task)

    def _add_task(self, task: asyncio.Task[typing.Any], /) -> None:
        if not task.done():
            self._tasks.append(task)
            task.add_done_callback(self._remove_task)

    async def _on_starting(self, _: hikari.StartingEvent, /) -> None:
        self.open()

    async def _on_stopping(self, _: hikari.StoppingEvent, /) -> None:
        self.close()

    async def _gc(self) -> None:
        while True:
            for custom_id, modal in tuple(self._modals.items()):
                if not modal.has_expired or custom_id not in self._modals:
                    continue

                del self._modals[custom_id]
                # This may slow this gc task down but the more we yield the better.
                # await modal.close()  # TODO: this

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

    def _match_constant_id(self, custom_id: str) -> typing.Optional[AbstractModal]:
        return self._constant_ids.get(custom_id) or self._prefix_ids.get(
            next(filter(custom_id.startswith, self._prefix_ids.keys()), "")
        )

    async def _execute_modal(
        self,
        modal: AbstractModal,
        interaction: hikari.ModalInteraction,
        /,
        *,
        future: typing.Optional[asyncio.Future[ModalResponseT]] = None,
    ) -> None:
        ctx = ModalContext(self, interaction, self._add_task, response_future=future)

        try:
            await modal.execute(ctx)
        except ModalClosed:
            self._modals.pop(ctx.interaction.custom_id, None)

    async def _execute_constant_modal(
        self,
        modal: AbstractModal,
        interaction: hikari.ModalInteraction,
        /,
        *,
        future: typing.Optional[asyncio.Future[ModalResponseT]] = None,
    ) -> None:
        ctx = ModalContext(self, interaction, self._add_task, response_future=future)

        try:
            await modal.execute(ctx)
        except ModalClosed:
            _LOGGER.warning("Constant executor raised ModalClosed, you need to set `timeout` to None")

    async def on_gateway_event(self, event: hikari.InteractionCreateEvent, /) -> None:
        """Process an interaction create gateway event.

        Parameters
        ----------
        event
            The interaction create gateway event to process.
        """
        if not isinstance(event.interaction, hikari.ModalInteraction):
            return

        if constant_callback := self._match_constant_id(event.interaction.custom_id):
            ctx = ModalContext(self, event.interaction, self._add_task, ephemeral_default=False)
            await constant_callback.execute(ctx)

        elif modal := self._modals.get(event.interaction.custom_id):
            await self._execute_modal(modal, event.interaction)

        else:
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE, "This modal has timed-out.", flags=hikari.MessageFlag.EPHEMERAL
            )

    async def on_rest_request(self, interaction: hikari.ModalInteraction, /) -> ModalResponseT:
        """Process a modal interaction REST request.

        Parameters
        ----------
        interaction
            The interaction to process.

        Returns
        -------
        ResponseT
            The REST re sponse.
        """
        if modal := self._match_constant_id(interaction.custom_id):
            future: asyncio.Future[ModalResponseT] = asyncio.Future()
            self._add_task(asyncio.create_task(self._execute_constant_modal(modal, interaction, future=future)))
            return await future

        if modal := self._modals.get(interaction.custom_id):
            if not modal.has_expired:
                future = asyncio.Future()
                self._add_task(asyncio.create_task(self._execute_modal(modal, interaction, future=future)))
                return await future

            del self._modals[interaction.custom_id]

        return (
            interaction.build_response()
            .set_content("This modal has timed-out.")
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    def set_constant_id(self, custom_id: str, callback: AbstractModal, /, *, prefix_match: bool = False) -> Self:
        """Add a constant "custom_id" callback.

        These are callbacks which'll always be called for a specific custom_id
        while taking priority over executors.

        Parameters
        ----------
        custom_id
            The custom_id to register the callback for.
        callback
            The callback to register.

            This should take a single argument of type [yuyo.modals.ModalContext][],
            be asynchronous and return [None][].
        prefix_match
            Whether the custom_id should be treated as a prefix match.

            This allows for further state to be held in the custom id after the
            prefix and is lower priority than normal custom id match.

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

        if custom_id in self._constant_ids:
            raise ValueError(f"{custom_id!r} is already registered as a constant id")

        if prefix_match:
            self._prefix_ids[custom_id] = callback
            return self

        self._constant_ids[custom_id] = callback
        return self

    def get_constant_id(self, custom_id: str, /) -> typing.Optional[AbstractModal]:
        """Get a set constant "custom_id" callback.

        Parameters
        ----------
        custom_id
            The custom_id to get the callback for.

        Returns
        -------
        CallbackSig | None
            The callback for the custom_id, or [None][] if it doesn't exist.
        """
        return self._constant_ids.get(custom_id) or self._prefix_ids.get(custom_id)

    def remove_constant_id(self, custom_id: str, /) -> Self:
        """Remove a constant "custom_id" callback.

        Parameters
        ----------
        custom_id
            The custom_id to remove the callback for.

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
            del self._constant_ids[custom_id]
        except KeyError:
            del self._prefix_ids[custom_id]

        return self

    # def set_executor(
    #     self, message: hikari.SnowflakeishOr[hikari.Message], executor: AbstractModalExecutor, /
    # ) -> Self:
    #     """Set the modal executor for a message.

    #     Parameters
    #     ----------
    #     message
    #         The message to set the executor for.
    #     executor
    #         The executor to set.

    #         This will be called for every modal interaction for the message
    #         unless the modal's custom_id is registered as a constant id callback.

    #     Returns
    #     -------
    #     Self
    #         The modal client to allow chaining.
    #     """
    #     self._executors[int(message)] = executor
    #     return self

    # def get_executor(
    #     self, message: hikari.SnowflakeishOr[hikari.Message], /
    # ) -> typing.Optional[AbstractModalExecutor]:
    #     """Get the modal executor set for a message.

    #     Parameters
    #     ----------
    #     message
    #         The message to get the executor for.

    #     Returns
    #     -------
    #     yuyo.modals.AbstractModalExecutor | None
    #         The executor set for the message or [None][] if none is set.
    #     """
    #     return self._executors.get(int(message))

    # def remove_executor(self, message: hikari.SnowflakeishOr[hikari.Message], /) -> Self:
    #     """Remove the modal executor for a message.

    #     Parameters
    #     ----------
    #     message
    #         The message to remove the executor for.

    #     Returns
    #     -------
    #     Self
    #         The modal client to allow chaining.
    #     """
    #     self._executors.pop(int(message))
    #     return self


class ModalClosed(Exception):
    ...


class AbstractModal(abc.ABC):
    __slots__ = ()

    @property
    @abc.abstractmethod
    def has_expired(self) -> bool:
        """Whether this modal has ended."""

    @abc.abstractmethod
    async def execute(self, ctx: ModalContext) -> None:
        """Execute this modal.

        Parameters
        ----------
        ctx
            The context to execute this with.

        Raises
        ------
        ModalClosed
            If the modal is closed.
        """


class _TrackedField:
    __slots__ = ("custom_id", "default", "key", "prefix_match")

    def __init__(
        self, *, custom_id: str, default: typing.Union[typing.Any, NoDefault], key: str, prefix_match: bool
    ) -> None:
        self.custom_id = custom_id
        self.default = default
        self.key = key
        self.prefix_match = prefix_match


class Modal(AbstractModal, typing.Generic[_CallbackSigT]):
    """Temp"""

    __slots__ = (
        "_callback",
        "_created_at",
        "_ephemeral_default",
        "_last_triggered",
        "_prefix_match",
        "_rows",
        "_timeout",
        "_tracked_fields",
    )

    _all_static_fields: list[_TrackedField] = []
    _all_static_rows: list[hikari.impl.ModalActionRowBuilder] = []
    _static_fields: list[_TrackedField] = []
    _static_prefix_match = False
    _static_rows: list[hikari.impl.ModalActionRowBuilder] = []

    def __init__(
        self,
        callback: _CallbackSigT,
        /,
        *,
        ephemeral_default: bool = False,
        timeout: typing.Optional[datetime.timedelta] = datetime.timedelta(seconds=10),
    ) -> None:
        """Initialise a component executor.

        Parameters
        ----------
        ephemeral_default
            Whether this executor's responses should default to being ephemeral.
        timeout
            How long this component should last until its marked as timed out.
        """
        self._callback = callback
        self._created_at = datetime.datetime.now(tz=datetime.timezone.utc)
        self._ephemeral_default = ephemeral_default
        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        self._prefix_match = False
        self._rows: list[hikari.impl.ModalActionRowBuilder] = []
        self._timeout = timeout
        self._tracked_fields: list[_TrackedField] = []

    def __init_subclass__(cls) -> None:
        cls._all_static_fields = []
        cls._all_static_rows = []
        cls._static_fields = []
        cls._static_prefix_match = False
        cls._static_rows = []

        for super_cls in cls.mro()[-2::-1]:
            if issubclass(super_cls, Modal):
                cls._static_prefix_match = cls._static_prefix_match or super_cls._static_prefix_match
                cls._all_static_fields.extend(super_cls._all_static_fields)
                cls._all_static_rows.extend(super_cls._all_static_rows)

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return (
            self._timeout is not None
            and self._timeout < datetime.datetime.now(tz=datetime.timezone.utc) - self._last_triggered
        )

    if typing.TYPE_CHECKING:
        __call__: _CallbackSigT

    else:

        async def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
            return await self._callback(*args, **kwargs)

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
        max_length: int = 1,
        prefix_match: bool = False,
        keyword: typing.Optional[str] = None,
    ) -> type[Self]:
        """Add a text input field to all instances and subclasses of this modal.

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
        min_length
            Minimum length the input text can be.

            This can be greater than or equal to 0 and less than or equal to 4000.
        max_length
            Maximum length the input text can be.

            This can be greater than or equal to 1 and less than or equal to 4000.
        prefix_match
            Whether `custom_id` should be matched as a prefix rather than through equal.
        keyword
            Name of the parameter the text for this field should be passed to.

            This will be of type [str][] and may also be the value passed for
            `default`.

        Returns
        -------
        Self
            The class to enable call chaining.
        """
        if cls is Modal:
            raise RuntimeError("Can only add static fields to subclasses")

        custom_id, row = _make_text_input(
            custom_id=custom_id,
            label=label,
            style=style,
            placeholder=placeholder,
            value=value,
            default=default,
            min_length=min_length,
            max_length=max_length,
        )

        if keyword:
            cls._static_fields.append(
                _TrackedField(custom_id=custom_id, default=default, key=keyword, prefix_match=prefix_match)
            )

        cls._static_rows.append(row)
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
        max_length: int = 1,
        prefix_match: bool = False,
        keyword: typing.Optional[str] = None,
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
        min_length
            Minimum length the input text can be.

            This can be greater than or equal to 0 and less than or equal to 4000.
        max_length
            Maximum length the input text can be.

            This can be greater than or equal to 1 and less than or equal to 4000.
        prefix_match
            Whether `custom_id` should be matched as a prefix rather than through equal.
        keyword
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
            value=value,
            default=default,
            min_length=min_length,
            max_length=max_length,
        )
        self._rows.append(row)

        if keyword:
            self._tracked_fields.append(
                _TrackedField(custom_id=custom_id, default=default, key=keyword, prefix_match=prefix_match)
            )

        return self

    async def execute(self, ctx: ModalContext) -> None:
        ctx.set_ephemeral_default(self._ephemeral_default)
        fields: dict[str, typing.Any] = {}
        compiled_prefixes: typing.Optional[dict[str, typing.Any]] = None

        for field in self._tracked_fields:
            if field.prefix_match:
                if compiled_prefixes is None:
                    compiled_prefixes = {itertools.chain}

        await ctx.client.alluka.call_with_async_di(self._callback, ctx, **fields)


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


# TODO: allow without parenthesis


def as_modal(
    *, ephemeral_default: bool = False, timeout: typing.Optional[datetime.timedelta] = datetime.timedelta(seconds=10)
) -> collections.Callable[[_CallbackSigT], Modal[_CallbackSigT]]:
    def decorator(callback: _CallbackSigT, /) -> Modal[_CallbackSigT]:
        return Modal(callback, ephemeral_default=ephemeral_default, timeout=timeout)

    return decorator


@as_modal()
async def callback(ctx: ModalContext) -> None:
    pass
