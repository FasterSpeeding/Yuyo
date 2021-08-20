# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020-2021, Faster Speeding
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

__all__: typing.Sequence[str] = [
    "AbstractComponentExecutor",
    "ActionRowExecutor",
    "as_child_executor",
    "as_component_callback",
    "ChildActionRowExecutor",
    "ComponentClient",
    "ComponentContext",
    "ComponentExecutor",
    "ComponentPaginator",
    "InteractiveButtonBuilder",
    "MultiComponentExecutor",
    "SelectMenuBuilder",
]

import abc
import asyncio
import datetime
import inspect
import itertools
import typing
import uuid

import hikari

from . import pagination

if typing.TYPE_CHECKING:
    import types

    from hikari import traits

    _T = typing.TypeVar("_T")

    class _ContainerProto(typing.Protocol):
        def add_callback(self: _T, _: str, __: CallbackSig, /) -> _T:
            raise NotImplementedError

        def add_component(self: _T, _: hikari.api.ComponentBuilder, /) -> _T:
            raise NotImplementedError

    class _ParentExecutorProto(typing.Protocol):
        def add_builder(self: _T, _: hikari.api.ComponentBuilder, /) -> _T:
            raise NotImplementedError

        def add_executor(self: _T, _: AbstractComponentExecutor, /) -> _T:
            raise NotImplementedError


def _random_id() -> str:
    return str(uuid.uuid4())


AbstractComponentExecutorT = typing.TypeVar("AbstractComponentExecutorT", bound="AbstractComponentExecutor")
CallbackSig = typing.Callable[["ComponentContext"], typing.Awaitable[None]]
CallbackSigT = typing.TypeVar("CallbackSigT", bound=CallbackSig)
ContainerProtoT = typing.TypeVar("ContainerProtoT", bound="_ContainerProto")
ParentExecutorProtoT = typing.TypeVar("ParentExecutorProtoT", bound="_ParentExecutorProto")
ResponseT = typing.Union[hikari.api.InteractionMessageBuilder, hikari.api.InteractionDeferredBuilder]


_ActionRowExecutorT = typing.TypeVar("_ActionRowExecutorT", bound="ActionRowExecutor")
_ComponentClientT = typing.TypeVar("_ComponentClientT", bound="ComponentClient")
_ComponentExecutorT = typing.TypeVar("_ComponentExecutorT", bound="ComponentExecutor")
_MultiComponentExecutorT = typing.TypeVar("_MultiComponentExecutorT", bound="MultiComponentExecutor")


class ComponentContext:
    __slots__ = (
        "_ephemeral_default",
        "_has_responded",
        "_has_been_deferred",
        "_interaction",
        "_last_response_id",
        "_response_future",
        "_response_lock",
    )

    def __init__(
        self,
        *,
        ephemeral_default: bool,
        interaction: hikari.ComponentInteraction,
        response_future: typing.Optional[asyncio.Future[ResponseT]] = None,
    ) -> None:
        self._ephemeral_default = ephemeral_default
        self._has_responded = False
        self._has_been_deferred = False
        self._interaction = interaction
        self._last_response_id: typing.Optional[hikari.Snowflake] = None
        self._response_future = response_future
        self._response_lock = asyncio.Lock()

    @property
    def has_been_deferred(self) -> bool:
        return self._has_been_deferred

    @property
    def has_responded(self) -> bool:
        return self._has_responded

    @property
    def interaction(self) -> hikari.ComponentInteraction:
        return self._interaction

    def _get_flags(self, flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag]) -> int:
        if flags is not hikari.UNDEFINED:
            assert isinstance(flags, int)
            return flags

        return hikari.MessageFlag.EPHEMERAL if self._ephemeral_default else hikari.MessageFlag.NONE

    async def defer(
        self,
        defer_type: hikari.DeferredResponseTypesT,
        flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag] = hikari.UNDEFINED,
    ) -> None:
        flags = self._get_flags(flags)
        async with self._response_lock:
            if self._has_been_deferred:
                raise RuntimeError("Context has already been responded to")

            self._has_been_deferred = True
            if self._response_future:
                self._response_future.set_result(self._interaction.build_deferred_response(defer_type).set_flags(flags))

            else:
                await self._interaction.create_initial_response(defer_type, flags=flags)

    async def create_followup(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        attachment: hikari.UndefinedOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedOr[typing.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[typing.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[typing.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialUser], bool]
        ] = hikari.UNDEFINED,
        role_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialRole], bool]
        ] = hikari.UNDEFINED,
        tts: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag] = hikari.UNDEFINED,
    ) -> hikari.Message:
        async with self._response_lock:
            message = await self._interaction.execute(
                content=content,
                attachment=attachment,
                attachments=attachments,
                component=component,
                components=components,
                embed=embed,
                embeds=embeds,
                flags=self._get_flags(flags),
                tts=tts,
                mentions_everyone=mentions_everyone,
                user_mentions=user_mentions,
                role_mentions=role_mentions,
            )
            self._last_response_id = message.id
            return message

    async def _create_initial_response(
        self,
        response_type: hikari.ComponentResponseTypesT,
        /,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[typing.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[typing.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialUser], bool]
        ] = hikari.UNDEFINED,
        role_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialRole], bool]
        ] = hikari.UNDEFINED,
        flags: typing.Union[int, hikari.MessageFlag, hikari.UndefinedType] = hikari.UNDEFINED,
        tts: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
    ) -> None:
        flags = self._get_flags(flags)
        if self._has_responded:
            raise RuntimeError("Initial response has already been created")

        if self._has_been_deferred:
            raise RuntimeError(
                "edit_initial_response must be used to set the initial response after a context has been deferred"
            )

        self._has_responded = True
        if not self._response_future:
            await self._interaction.create_initial_response(
                response_type=response_type,
                content=content,
                component=component,
                components=components,
                embed=embed,
                embeds=embeds,
                flags=flags,
                tts=tts,
                mentions_everyone=mentions_everyone,
                user_mentions=user_mentions,
                role_mentions=role_mentions,
            )

        else:
            if component and components:
                raise ValueError("Only one of component or components may be passed")

            if embed and embeds:
                raise ValueError("Only one of embed or embeds may be passed")

            if component:
                assert not isinstance(component, hikari.UndefinedType)
                components = (component,)

            if embed:
                assert not isinstance(embed, hikari.UndefinedType)
                embeds = (embed,)

            # Pyright doesn't properly support attrs and doesn't account for _ being removed from field
            # pre-fix in init.
            result = hikari.impl.InteractionMessageBuilder(
                type=response_type,  # type: ignore
                content=content,  # type: ignore
                components=components,  # type: ignore
                embeds=embeds,  # type: ignore
                flags=flags,  # type: ignore
                is_tts=tts,  # type: ignore
                mentions_everyone=mentions_everyone,  # type: ignore
                user_mentions=user_mentions,  # type: ignore
                role_mentions=role_mentions,  # type: ignore
            )  # type: ignore

            self._response_future.set_result(result)

    async def create_initial_response(
        self,
        response_type: hikari.ComponentResponseTypesT,
        /,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[typing.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[typing.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialUser], bool]
        ] = hikari.UNDEFINED,
        role_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialRole], bool]
        ] = hikari.UNDEFINED,
        flags: typing.Union[int, hikari.MessageFlag, hikari.UndefinedType] = hikari.UNDEFINED,
        tts: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
    ) -> None:
        async with self._response_lock:
            await self._create_initial_response(
                response_type,
                content=content,
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

    async def delete_initial_response(self) -> None:
        await self._interaction.delete_initial_response()

    async def delete_last_response(self) -> None:
        if self._last_response_id is None:
            if self._has_responded:
                await self._interaction.delete_initial_response()
                return

            raise LookupError("Context has no last response")

        await self._interaction.delete_message(self._last_response_id)

    async def edit_initial_response(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        attachment: hikari.UndefinedOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedOr[typing.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[typing.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[typing.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        replace_attachments: bool = False,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialUser], bool]
        ] = hikari.UNDEFINED,
        role_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialRole], bool]
        ] = hikari.UNDEFINED,
    ) -> hikari.Message:
        result = await self._interaction.edit_initial_response(
            content=content,
            attachment=attachment,
            attachments=attachments,
            component=component,
            components=components,
            embed=embed,
            embeds=embeds,
            replace_attachments=replace_attachments,
            mentions_everyone=mentions_everyone,
            user_mentions=user_mentions,
            role_mentions=role_mentions,
        )
        self._has_responded = True
        return result

    async def edit_last_response(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        attachment: hikari.UndefinedOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedOr[typing.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[typing.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[typing.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        replace_attachments: bool = False,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialUser], bool]
        ] = hikari.UNDEFINED,
        role_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialRole], bool]
        ] = hikari.UNDEFINED,
    ) -> hikari.Message:
        if self._last_response_id:
            return await self._interaction.edit_message(
                self._last_response_id,
                content=content,
                attachment=attachment,
                attachments=attachments,
                component=component,
                components=components,
                embed=embed,
                embeds=embeds,
                replace_attachments=replace_attachments,
                mentions_everyone=mentions_everyone,
                user_mentions=user_mentions,
                role_mentions=role_mentions,
            )

        if self._has_responded:
            return await self.edit_initial_response(
                content=content,
                attachment=attachment,
                attachments=attachments,
                component=component,
                components=components,
                embed=embed,
                embeds=embeds,
                replace_attachments=replace_attachments,
                mentions_everyone=mentions_everyone,
                user_mentions=user_mentions,
                role_mentions=role_mentions,
            )

        raise LookupError("Context has no previous responses")

    async def fetch_initial_response(self) -> hikari.Message:
        return await self._interaction.fetch_initial_response()

    async def fetch_last_response(self) -> hikari.Message:
        if self._last_response_id is not None:
            return await self._interaction.fetch_message(self._last_response_id)

        if self._has_responded:
            return await self.fetch_initial_response()

        raise LookupError("Context has no previous known responses")

    @typing.overload
    async def respond(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        ensure_result: typing.Literal[False] = False,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[typing.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[typing.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialUser], bool]
        ] = hikari.UNDEFINED,
        role_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialRole], bool]
        ] = hikari.UNDEFINED,
    ) -> typing.Optional[hikari.Message]:
        ...

    @typing.overload
    async def respond(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        ensure_result: typing.Literal[True],
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[typing.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[typing.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialUser], bool]
        ] = hikari.UNDEFINED,
        role_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialRole], bool]
        ] = hikari.UNDEFINED,
    ) -> hikari.Message:
        ...

    async def respond(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        ensure_result: bool = False,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[typing.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[typing.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialUser], bool]
        ] = hikari.UNDEFINED,
        role_mentions: hikari.UndefinedOr[
            typing.Union[hikari.SnowflakeishSequence[hikari.PartialRole], bool]
        ] = hikari.UNDEFINED,
    ) -> typing.Optional[hikari.Message]:
        async with self._response_lock:
            if self._has_responded:
                message = await self._interaction.execute(
                    content,
                    component=component,
                    components=components,
                    embed=embed,
                    embeds=embeds,
                    mentions_everyone=mentions_everyone,
                    user_mentions=user_mentions,
                    role_mentions=role_mentions,
                )
                self._last_response_id = message.id
                return message

            if self._has_been_deferred:
                return await self.edit_initial_response(
                    content=content,
                    component=component,
                    components=components,
                    embed=embed,
                    embeds=embeds,
                    mentions_everyone=mentions_everyone,
                    user_mentions=user_mentions,
                    role_mentions=role_mentions,
                )

            await self._create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                content=content,
                component=component,
                components=components,
                embed=embed,
                embeds=embeds,
                mentions_everyone=mentions_everyone,
                user_mentions=user_mentions,
                role_mentions=role_mentions,
            )

        if ensure_result:
            return await self._interaction.fetch_initial_response()


class ExecutorClosed(Exception):
    ...


class ComponentClient:
    __slots__ = ("_event_manager", "_executors", "_gc_task", "_server")

    def __init__(
        self,
        *,
        event_manager: typing.Optional[hikari.api.EventManager] = None,
        server: typing.Optional[hikari.api.InteractionServer] = None,
    ) -> None:
        self._event_manager = event_manager
        self._executors: typing.Dict[int, AbstractComponentExecutor] = {}
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._server = server

    def __enter__(self) -> None:
        self.open()

    async def __exit__(
        self,
        exc_type: typing.Optional[type[BaseException]],
        exc: typing.Optional[BaseException],
        exc_traceback: typing.Optional[types.TracebackType],
    ) -> None:
        self.close()

    @classmethod
    def from_gateway_bot(cls, bot: traits.GatewayBotAware, /) -> ComponentClient:
        return cls(event_manager=bot.event_manager)

    @classmethod
    def from_rest_bot(cls, bot: traits.RESTBotAware, /) -> ComponentClient:
        return cls(server=bot.interaction_server)

    async def _gc(self) -> None:
        while True:
            for message_id, executor in tuple(self._executors.items()):
                if executor.has_expired or message_id not in self._executors:
                    continue

                del self._executors[message_id]
                # This may slow this gc task down but the more we yield the better.
                # await executor.close()  # TODO: this

            await asyncio.sleep(5)  # TODO: is this a good time?

    def close(self) -> None:
        if self._gc_task:
            self._gc_task.cancel()
            self._gc_task = None

        if self._server:
            self._server.set_listener(hikari.ComponentInteraction, None)

        if self._event_manager:
            self._event_manager.unsubscribe(hikari.InteractionCreateEvent, self.on_gateway_event)

        # executor = self._executors
        self._executors = {}
        # for executor in executor.values():  # TODO: finish
        #     executor.close()

    def open(self) -> None:
        if self._server:
            self._server.set_listener(hikari.ComponentInteraction, self.on_rest_request)

        if self._event_manager:
            self._event_manager.subscribe(hikari.InteractionCreateEvent, self.on_gateway_event)

    async def _execute_executor(
        self,
        executor: AbstractComponentExecutor,
        interaction: hikari.ComponentInteraction,
        /,
        future: typing.Optional[asyncio.Future[ResponseT]] = None,
    ) -> None:
        try:
            await executor.execute(interaction, future=future)
        except ExecutorClosed:
            self._executors.pop(interaction.message_id, None)

    async def on_gateway_event(self, event: hikari.InteractionCreateEvent, /) -> None:
        if not isinstance(event.interaction, hikari.ComponentInteraction):
            return

        if executor := self._executors.get(event.interaction.message_id):
            await self._execute_executor(executor, event.interaction)

    async def on_rest_request(self, interaction: hikari.ComponentInteraction, /) -> ResponseT:
        future: asyncio.Future[ResponseT] = asyncio.Future()
        if executor := self._executors.get(interaction.message_id):
            if executor.has_expired:
                del self._executors[interaction.message_id]
                raise LookupError("Not found")

            execution_task = asyncio.create_task(self._execute_executor(executor, interaction, future=future))
            done, _ = asyncio.wait((future, execution_task), return_when=asyncio.FIRST_COMPLETED)

            if future in done:
                execution_task.cancel()
                return await future

            raise RuntimeError("Execution finished without setting a response")

        # TODO: gonna need a way to mark as giving an error response on hikari without actually erroring
        raise LookupError("Not found")

    def add_executor(
        self: _ComponentClientT, message: hikari.SnowflakeishOr[hikari.Message], executor: AbstractComponentExecutor, /
    ) -> _ComponentClientT:
        self._executors[int(message)] = executor
        return self


def as_component_callback(custom_id: str, /) -> typing.Callable[[CallbackSigT], CallbackSigT]:
    def decorator(callback: CallbackSigT, /) -> CallbackSigT:
        callback.__custom_id__ = custom_id
        return callback

    return decorator


class AbstractComponentExecutor(abc.ABC):
    __slots__ = ()

    @property
    def custom_ids(self) -> typing.Collection[str]:
        raise NotImplementedError

    @property
    def has_expired(self) -> bool:
        raise NotImplementedError

    async def execute(
        self, _: hikari.ComponentInteraction, /, *, future: typing.Optional[asyncio.Future[ResponseT]] = None
    ) -> None:
        raise NotImplementedError


class ComponentExecutor(AbstractComponentExecutor):
    __slots__ = ("_id_to_callback", "_last_triggered", "_lock", "_timeout")

    def __init__(
        self, *, load_from_attributes: bool = True, timeout: datetime.timedelta = datetime.timedelta(seconds=30)
    ) -> None:
        self._id_to_callback: dict[str, CallbackSig] = {}
        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        self._lock = asyncio.Lock()
        self._timeout = timeout
        if load_from_attributes and type(self) is not ComponentExecutor:
            for _, value in inspect.getmembers(self):  # TODO: might be a tad bit slow
                try:
                    custom_id = value.__custom_id__

                except AttributeError:
                    pass

                else:
                    self._id_to_callback[custom_id] = value

    @property
    def callbacks(self) -> typing.Mapping[str, CallbackSig]:
        return self._id_to_callback.copy()

    @property
    def custom_ids(self) -> typing.Collection[str]:
        return self._id_to_callback.keys()

    @property
    def has_expired(self) -> bool:
        """Whether this executor has ended.

        Returns
        -------
        bool
            Whether this executor has ended.
        """
        return self._timeout < datetime.datetime.now(tz=datetime.timezone.utc) - self._last_triggered

    async def execute(
        self, interaction: hikari.ComponentInteraction, /, *, future: typing.Optional[asyncio.Future[ResponseT]] = None
    ) -> None:
        ctx = ComponentContext(ephemeral_default=False, interaction=interaction, response_future=future)
        callback = self._id_to_callback[interaction.custom_id]
        await callback(ctx)

    def add_callback(self: _ComponentExecutorT, id_: str, callback: CallbackSig, /) -> _ComponentExecutorT:
        self._id_to_callback[id_] = callback
        return self

    def with_callback(self, id_: str, /) -> typing.Callable[[CallbackSigT], CallbackSigT]:
        def decorator(callback: CallbackSigT, /) -> CallbackSigT:
            self.add_callback(id_, callback)
            return callback

        return decorator


class InteractiveButtonBuilder(hikari.impl.InteractiveButtonBuilder[ContainerProtoT]):
    __slots__ = ("_callback",)

    def __init__(
        self, callback: CallbackSig, container: ContainerProtoT, custom_id: str, style: hikari.ButtonStyle
    ) -> None:
        self._callback = callback
        # pyright doesn't support attrs _ kwargs
        super().__init__(container=container, custom_id=custom_id, style=style)  # type: ignore

    @property
    def callback(self) -> CallbackSig:
        return self._callback

    def add_to_container(self) -> ContainerProtoT:
        self._container.add_callback(self.custom_id, self.callback)
        return super().add_to_container()


class SelectMenuBuilder(hikari.impl.SelectMenuBuilder[ContainerProtoT]):
    __slots__ = ("_callback",)

    def __init__(self, callback: CallbackSig, container: ContainerProtoT, custom_id: str) -> None:
        self._callback = callback
        # pyright doesn't support attrs _ kwargs
        super().__init__(container=container, custom_id=custom_id)  # type: ignore

    @property
    def callback(self) -> CallbackSig:
        return self._callback

    def add_to_container(self) -> ContainerProtoT:
        self._container.add_callback(self.custom_id, self.callback)
        return super().add_to_container()


class ActionRowExecutor(ComponentExecutor, hikari.api.ComponentBuilder):
    __slots__ = ("_components", "_stored_type")

    def __init__(
        self, *, load_from_attributes: bool = False, timeout: datetime.timedelta = datetime.timedelta(seconds=30)
    ) -> None:
        super().__init__(load_from_attributes=load_from_attributes, timeout=timeout)
        self._components: typing.List[hikari.api.ComponentBuilder] = []
        self._stored_type: typing.Optional[hikari.ComponentType] = None

    @property
    def components(self) -> typing.Sequence[hikari.api.ComponentBuilder]:
        return self._components.copy()

    def _assert_can_add_type(self, type_: hikari.ComponentType, /) -> None:
        if self._stored_type is not None and self._stored_type != type_:
            raise ValueError(f"{type_} component type cannot be added to a container which already holds {type_}")

        self._stored_type = type_

    def add_component(self: _ActionRowExecutorT, component: hikari.api.ComponentBuilder, /) -> _ActionRowExecutorT:
        self._components.append(component)
        return self

    @typing.overload
    def add_button(
        self: _ActionRowExecutorT,
        style: hikari.InteractiveButtonTypesT,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
    ) -> InteractiveButtonBuilder[_ActionRowExecutorT]:
        ...

    @typing.overload
    def add_button(
        self: _ActionRowExecutorT,
        style: typing.Union[typing.Literal[hikari.ButtonStyle.LINK], typing.Literal[5]],
        url: str,
        /,
    ) -> hikari.impl.LinkButtonBuilder[_ActionRowExecutorT]:
        ...

    def add_button(
        self: _ActionRowExecutorT,
        style: typing.Union[int, hikari.ButtonStyle],
        callback_or_url: typing.Union[CallbackSig, str],
        *,
        custom_id: typing.Optional[str] = None,
    ) -> typing.Union[
        hikari.impl.LinkButtonBuilder[_ActionRowExecutorT], InteractiveButtonBuilder[_ActionRowExecutorT]
    ]:
        self._assert_can_add_type(hikari.ComponentType.BUTTON)
        if style in hikari.InteractiveButtonTypes:
            # Pyright doesn't properly support _ attrs kwargs
            if custom_id is None:
                custom_id = _random_id()

            if not isinstance(callback_or_url, typing.Callable):
                raise ValueError(f"Callback must be passed for an interactive button, not {type(callback_or_url)}")

            return InteractiveButtonBuilder(
                callback=callback_or_url, container=self, style=style, custom_id=custom_id  # type: ignore
            )

        # Pyright doesn't properly support _ attrs kwargs
        if not isinstance(callback_or_url, str):
            raise ValueError(f"String url must be passed for Link style buttons, not {type(callback_or_url)}")

        return hikari.impl.LinkButtonBuilder(container=self, style=style, url=callback_or_url)  # type: ignore

    def add_select_menu(
        self: _ActionRowExecutorT, callback: CallbackSig, /, custom_id: typing.Optional[str] = None
    ) -> SelectMenuBuilder[_ActionRowExecutorT]:
        self._assert_can_add_type(hikari.ComponentType.SELECT_MENU)
        if custom_id is None:
            custom_id = _random_id()

        return SelectMenuBuilder(callback=callback, container=self, custom_id=custom_id)

    def build(self) -> typing.Dict[str, typing.Any]:
        return {
            "type": hikari.ComponentType.ACTION_ROW,
            "components": [component.build() for component in self._components],
        }


class ChildActionRowExecutor(ActionRowExecutor, typing.Generic[ParentExecutorProtoT]):
    __slots__ = ("_parent",)

    def __init__(self, parent: ParentExecutorProtoT, *, load_from_attributes: bool = False) -> None:
        super().__init__(load_from_attributes=load_from_attributes)
        self._parent = parent

    def add_to_parent(self) -> ParentExecutorProtoT:
        return self._parent.add_executor(self).add_builder(self)


def as_child_executor(executor: typing.Type[AbstractComponentExecutorT], /) -> typing.Type[AbstractComponentExecutorT]:
    executor.__is_child_executor__ = True  # type: ignore
    return executor


class MultiComponentExecutor(AbstractComponentExecutor):
    __slots__ = ("_executors", "_last_triggered", "_lock", "_timeout")

    def __init__(
        self,
        *,
        load_from_attributes: bool = False,
        timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    ) -> None:
        self._builders: typing.List[hikari.api.ComponentBuilder] = []
        self._executors: typing.List[AbstractComponentExecutor] = []
        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        self._lock = asyncio.Lock()
        self._timeout = timeout
        if load_from_attributes and type(self) is not MultiComponentExecutor:
            for _, value in inspect.getmembers(self):  # TODO: might be a tad bit slow
                try:
                    if value.__is_child_executor__:
                        self._executors.append(value())

                except AttributeError:
                    pass

    @property
    def builders(self) -> typing.Collection[hikari.api.ComponentBuilder]:
        return self._builders

    @property
    def custom_ids(self) -> typing.Collection[str]:
        return list(itertools.chain.from_iterable(component.custom_ids for component in self._executors))

    @property
    def executors(self) -> typing.Sequence[AbstractComponentExecutor]:
        return self._executors.copy()

    @property
    def has_expired(self) -> bool:
        """Whether this executor has ended.

        Returns
        -------
        bool
            Whether this executor has ended.
        """
        return self._timeout < datetime.datetime.now(tz=datetime.timezone.utc) - self._last_triggered

    def add_builder(
        self: _MultiComponentExecutorT, builder: hikari.api.ComponentBuilder, /
    ) -> _MultiComponentExecutorT:
        self._builders.append(builder)
        return self

    def add_action_row(self: _MultiComponentExecutorT) -> ChildActionRowExecutor[_MultiComponentExecutorT]:
        return ChildActionRowExecutor(self)

    def add_executor(
        self: _MultiComponentExecutorT, executor: AbstractComponentExecutor, /
    ) -> _MultiComponentExecutorT:
        self._executors.append(executor)
        return self

    async def execute(
        self, interaction: hikari.ComponentInteraction, /, *, future: typing.Optional[asyncio.Future[ResponseT]] = None
    ) -> None:
        for executor in self._executors:
            if interaction.custom_id in executor.custom_ids:
                await executor.execute(interaction, future=future)
                return

        raise KeyError("Custom ID not found")


class ComponentPaginator(ActionRowExecutor):
    __slots__ = ("_authors", "_buffer", "_index", "_iterator", "_lock")

    def __init__(
        self,
        iterator: pagination.IteratorT[pagination.EntryT],
        *,
        authors: typing.Iterable[hikari.SnowflakeishOr[hikari.User]],
        triggers: typing.Collection[str] = (
            pagination.LEFT_TRIANGLE,
            pagination.STOP_SQUARE,
            pagination.RIGHT_TRIANGLE,
        ),
        load_from_attributes: bool = False,
        timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    ) -> None:
        super().__init__(load_from_attributes=load_from_attributes, timeout=timeout)

        self._authors = set(map(hikari.Snowflake, authors))
        self._buffer: typing.List[pagination.EntryT] = []
        self._index: int = 0
        self._iterator: typing.Optional[pagination.IteratorT[pagination.EntryT]] = iterator
        self._lock = asyncio.Lock()

        if pagination.LEFT_DOUBLE_TRIANGLE in triggers:
            self.add_button(hikari.ButtonStyle.SECONDARY, self._on_first).set_emoji(
                pagination.LEFT_DOUBLE_TRIANGLE
            ).add_to_container()

        if pagination.LEFT_TRIANGLE in triggers:
            self.add_button(hikari.ButtonStyle.SECONDARY, self._on_previous).set_emoji(
                pagination.LEFT_TRIANGLE
            ).add_to_container()

        if pagination.STOP_SQUARE in triggers:
            self.add_button(hikari.ButtonStyle.DANGER, self._on_disable).set_emoji(
                pagination.BLACK_CROSS
            ).add_to_container()

        if pagination.RIGHT_TRIANGLE in triggers:
            self.add_button(hikari.ButtonStyle.SECONDARY, self._on_next).set_emoji(
                pagination.RIGHT_TRIANGLE
            ).add_to_container()

        if pagination.RIGHT_DOUBLE_TRIANGLE in triggers:
            self.add_button(hikari.ButtonStyle.SECONDARY, self._on_last).set_emoji(
                pagination.RIGHT_DOUBLE_TRIANGLE
            ).add_to_container()

    async def execute(
        self, interaction: hikari.ComponentInteraction, /, *, future: asyncio.Future[ResponseT] = None
    ) -> None:
        if self._authors and interaction.user.id not in self._authors:
            await interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE, "You cannot use this button", flags=hikari.MessageFlag.EPHEMERAL
            )
            return

        await super().execute(interaction, future=future)

    async def get_next_entry(self, /) -> typing.Optional[pagination.EntryT]:
        # Check to see if we're behind the buffer before trying to go forward in the generator.
        if len(self._buffer) >= self._index + 2:
            self._index += 1
            return self._buffer[self._index]

        # If entry is not None then the generator's position was pushed forwards.
        if self._iterator and (entry := await pagination.seek_iterator(self._iterator, default=None)):
            self._index += 1
            self._buffer.append(entry)
            return entry

    @staticmethod
    def _noop(ctx: ComponentContext) -> typing.Awaitable[None]:
        return ctx.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE)

    async def _on_first(self, ctx: ComponentContext, /) -> None:
        if self._index != 0 and (first_entry := self._buffer[0] if self._buffer else await self.get_next_entry()):
            self._index = 0
            content, embed = first_entry
            await ctx.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE, content=content, embed=embed)

        else:
            await self._noop(ctx)

    async def _on_previous(self, ctx: ComponentContext, /) -> None:
        if self._index > 0:
            self._index -= 1
            content, embed = self._buffer[self._index]
            await ctx.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE, content=content, embed=embed)

        else:
            await self._noop(ctx)

    async def _on_disable(self, ctx: ComponentContext, /) -> None:
        self._iterator = None
        await ctx.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE, components=[])
        raise ExecutorClosed

    async def _on_last(self, ctx: ComponentContext, /) -> None:
        if self._iterator:
            # TODO: option to not lock on last
            loading_component = (
                ctx.interaction.app.rest.build_action_row()
                .add_button(hikari.ButtonStyle.PRIMARY, "loading")
                .set_is_disabled(True)
                .set_emoji(585958072850317322)
                .add_to_container()
            )
            await ctx.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE, component=loading_component)
            self._buffer.extend(await pagination.collect_iterator(self._iterator))
            self._index = len(self._buffer) - 1
            self._iterator = None

            if self._buffer:
                content, embed = self._buffer[self._index]
                await ctx.edit_initial_response(component=self, content=content, embed=embed)

            else:
                await ctx.edit_initial_response(component=self)

        elif self._buffer:
            self._index = len(self._buffer) - 1
            content, embed = self._buffer[-1]
            await ctx.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE, content=content, embed=embed)

        else:
            await self._noop(ctx)

    async def _on_next(self, ctx: ComponentContext, /) -> None:
        if entry := await self.get_next_entry():
            await ctx.defer(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
            content, embed = entry
            await ctx.edit_initial_response(content=content, embed=embed)

        else:
            await self._noop(ctx)
