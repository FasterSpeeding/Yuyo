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
"""Higher level client for callback based component execution."""
from __future__ import annotations

__all__: typing.Sequence[str] = [
    "AbstractComponentExecutor",
    "ActionRowExecutor",
    "ChildActionRowExecutor",
    "ComponentClient",
    "ComponentContext",
    "ComponentExecutor",
    "ComponentPaginator",
    "InteractiveButtonBuilder",
    "MultiComponentExecutor",
    "SelectMenuBuilder",
    "WaitFor",
    "WaitForExecutor",
    "as_child_executor",
    "as_component_callback",
]

import abc
import asyncio
import datetime
import inspect
import itertools
import os
import typing
import uuid
import warnings

import hikari

from . import pagination

if typing.TYPE_CHECKING:
    import types

    _T = typing.TypeVar("_T")
    _ActionRowExecutorT = typing.TypeVar("_ActionRowExecutorT", bound="ActionRowExecutor")
    _ComponentClientT = typing.TypeVar("_ComponentClientT", bound="ComponentClient")
    _ComponentExecutorT = typing.TypeVar("_ComponentExecutorT", bound="ComponentExecutor")
    _MultiComponentExecutorT = typing.TypeVar("_MultiComponentExecutorT", bound="MultiComponentExecutor")

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
CallbackSig = typing.Callable[["ComponentContext"], typing.Coroutine[typing.Any, typing.Any, None]]
CallbackSigT = typing.TypeVar("CallbackSigT", bound=CallbackSig)
ContainerProtoT = typing.TypeVar("ContainerProtoT", bound="_ContainerProto")
ParentExecutorProtoT = typing.TypeVar("ParentExecutorProtoT", bound="_ParentExecutorProto")
ResponseT = typing.Union[hikari.api.InteractionMessageBuilder, hikari.api.InteractionDeferredBuilder]


class ComponentContext:
    """The general context passed around for a component trigger."""

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
        """Whether this context's initial response has been deferred.

        This will be true if [yuyo.components.ComponentContext.defer][] has been called.
        """
        return self._has_been_deferred

    @property
    def has_responded(self) -> bool:
        """Whether an initial response has been made to this context yet.

        It's worth noting that a context must be either responded to or
        deferred within 3 seconds from it being received otherwise it'll be
        marked as failed.

        This will be true if either [yuyo.components.ComponentContext.respond][],
        [yuyo.components.ComponentContext.create_initial_response][] or
        [yuyo.components.ComponentContext.edit_initial_response][]
        (after a deferral) has been called.
        """
        return self._has_responded

    @property
    def interaction(self) -> hikari.ComponentInteraction:
        """Object of the interaction this context is for."""
        return self._interaction

    def _get_flags(self, flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag]) -> int:
        if flags is not hikari.UNDEFINED:
            assert isinstance(flags, int)
            return flags

        return hikari.MessageFlag.EPHEMERAL if self._ephemeral_default else hikari.MessageFlag.NONE

    async def defer(
        self,
        defer_type: hikari.DeferredResponseTypesT,
        /,
        *,
        flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag] = hikari.UNDEFINED,
    ) -> None:
        """Mark this context as deferred.

        Parameters
        ----------
        defer_type
            The type of deferral this should be.

            This may any of the following
            * [ResponseType.DEFERRED_MESSAGE_CREATE][hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_CREATE]
                to indicate that the following up call to
                [yuyo.components.ComponentContext.edit_initial_response][]
                or [yuyo.components.ComponentContext.respond][] should create
                a new message.
            * [ResponseType.DEFERRED_MESSAGE_UPDATE][hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE]
                to indicate that the following call to the aforementioned
                methods should update the existing message.
        flags
            The flags to set for this deferral.

            As of writing, the only message flag which can be set here is
            [hikari.messages.MessageFlag.EPHEMERAL][] which indicates that the deferred
            message create should be only visible by the interaction's author.
        """
        flags = self._get_flags(flags)
        async with self._response_lock:
            if self._has_been_deferred or self._has_responded:
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
        user_mentions: typing.Union[
            hikari.SnowflakeishSequence[hikari.PartialUser], bool, hikari.UndefinedType
        ] = hikari.UNDEFINED,
        role_mentions: typing.Union[
            hikari.SnowflakeishSequence[hikari.PartialRole], bool, hikari.UndefinedType
        ] = hikari.UNDEFINED,
        tts: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag] = hikari.UNDEFINED,
    ) -> hikari.Message:
        """Create a followup response for this context.

        !!! warning
            Calling this on a context which hasn't had an initial response yet
            will lead to a [hikari.errors.NotFoundError][] being raised.

        Parameters
        ----------
        content
            If provided, the message contents. If
            [hikari.undefined.UNDEFINED][], then nothing will be sent
            in the content. Any other value here will be cast to a
            [str][].

            If this is a [hikari.embeds.Embed][] and no `embed` kwarg is
            provided, then this will instead update the embed. This allows for
            simpler syntax when sending an embed alone.

            Likewise, if this is a [hikari.files.Resource][], then the
            content is instead treated as an attachment if no `attachment` and
            no `attachments` kwargs are provided.
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
        mentions_everyone
            If provided, whether the message should parse @everyone/@here
            mentions.
        user_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake][], or [hikari.users.PartialUser][]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.
            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake][], or [hikari.guilds.PartialRole][]
            derivatives to enforce mentioning specific roles.
        tts
            If provided, whether the message will be sent as a TTS message.
        flags
            The flags to set for this response.

            As of writing this can only flag which can be provided is EPHEMERAL,
            other flags are just ignored.

        Returns
        -------
        hikari.Message
            The created message object.

        Raises
        ------
        hikari.NotFoundError
            If the current interaction is not found or it hasn't had an initial
            response yet.
        hikari.BadRequestError
            This can be raised if the file is too large; if the embed exceeds
            the defined limits; if the message content is specified only and
            empty or greater than `2000` characters; if neither content, file
            or embeds are specified.
            If any invalid snowflake IDs are passed; a snowflake may be invalid
            due to it being outside of the range of a 64 bit integer.
        ValueError
            If more than 100 unique objects/entities are passed for
            `role_mentions` or `user_mentions.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        """
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
        attachment: hikari.UndefinedOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedOr[typing.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[typing.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedOr[typing.Sequence[hikari.Embed]] = hikari.UNDEFINED,
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
        flags = self._get_flags(flags)
        if self._has_responded:
            raise RuntimeError("Initial response has already been created")

        if self._has_been_deferred:
            raise RuntimeError(
                "edit_initial_response must be used to set the initial response after a context has been deferred"
            )

        if not self._response_future:
            await self._interaction.create_initial_response(
                response_type=response_type,
                content=content,
                attachment=attachment,
                attachments=attachments,
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
            attachments = _to_list(attachment, attachments, content, _ATTACHMENT_TYPES, "attachment")
            components = _to_list(component, components, content, hikari.api.ComponentBuilder, "component")
            embeds = _to_list(embed, embeds, content, hikari.Embed, "embed")

            content = str(content) if content is not hikari.UNDEFINED else hikari.UNDEFINED
            # Pyright doesn't properly support attrs and doesn't account for _ being removed from field
            # pre-fix in init.
            result = hikari.impl.InteractionMessageBuilder(
                type=hikari.ResponseType.MESSAGE_CREATE,  # pyright: ignore reportGeneralTypeIssues
                content=content,  # pyright: ignore reportGeneralTypeIssues
                attachments=attachments,  # pyright: ignore reportGeneralTypeIssues
                components=components,  # pyright: ignore reportGeneralTypeIssues
                embeds=embeds,  # pyright: ignore reportGeneralTypeIssues
                flags=flags,  # pyright: ignore reportGeneralTypeIssues
                is_tts=tts,  # pyright: ignore reportGeneralTypeIssues
                mentions_everyone=mentions_everyone,  # pyright: ignore reportGeneralTypeIssues
                user_mentions=user_mentions,  # pyright: ignore reportGeneralTypeIssues
                role_mentions=role_mentions,  # pyright: ignore reportGeneralTypeIssues
            )

            self._response_future.set_result(result)

        self._has_responded = True

    async def create_initial_response(
        self,
        response_type: hikari.MessageResponseTypesT,
        /,
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
        hikari.RateLimitedError
            Usually, Hikari will handle and retry on hitting
            rate-limits automatically. This includes most bucket-specific
            rate-limits and global rate-limits. In some rare edge cases,
            however, Discord implements other undocumented rules for
            rate-limiting, such as limits per attribute. These cannot be
            detected or handled normally by Hikari due to their undocumented
            nature, and will trigger this exception if they occur.
        hikari.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        async with self._response_lock:
            await self._create_initial_response(
                response_type,
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

    async def delete_initial_response(self) -> None:
        """Delete the initial response after invoking this context.

        Raises
        ------
        LookupError, hikari.NotFoundError
            The last context has no initial response.
        """
        await self._interaction.delete_initial_response()
        # If they defer then delete the initial response, this should be treated as having
        # an initial response to allow for followup responses.
        self._has_responded = True

    async def delete_last_response(self) -> None:
        """Delete the last response after invoking this context.

        Raises
        ------
        LookupError, hikari.NotFoundError
            The last context has no responses.
        """
        if self._last_response_id is None:
            if self._has_responded or self._has_been_deferred:
                await self._interaction.delete_initial_response()
                # If they defer then delete the initial response then this should be treated as having
                # an initial response to allow for followup responses.
                self._has_responded = True
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
        """Edit the initial response for this context.

        Parameters
        ----------
        content
            The content to edit the initial response with.

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
        attachment
            A singular attachment to edit the initial response with.
        attachments
            A sequence of attachments to edit the initial response with.
        component
            If provided, builder object of the component to set for this message.
            This component will replace any previously set components and passing
            [None][] will remove all components.
        components
            If provided, a sequence of the component builder objects set for
            this message. These components will replace any previously set
            components and passing [None][] or an empty sequence will
            remove all components.
        embed
            An embed to replace the initial response with.
        embeds
            A sequence of embeds to replace the initial response with.
        replace_attachments
            Whether to replace the attachments of the response or not.
        mentions_everyone
            If provided, whether the message should parse @everyone/@here
            mentions.
        user_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.
            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake][], or [hikari.users.PartialUser][]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.
            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake][], or [hikari.guilds.PartialRole][]
            derivatives to enforce mentioning specific roles.

        Returns
        -------
        hikari.Message
            The message that has been edited.

        Raises
        ------
        ValueError
            If more than 100 unique objects/entities are passed for
            `role_mentions` or `user_mentions`.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        hikari.BadRequestError
            This may be raised in several discrete situations, such as messages
            being empty with no attachments or embeds; messages with more than
            2000 characters in them, embeds that exceed one of the many embed
            limits; too many attachments; attachments that are too large;
            invalid image URLs in embeds; too many components.
        hikari.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.ForbiddenError
            If you are missing the `SEND_MESSAGES` in the channel or the
            person you are trying to message has the DM's disabled.
        hikari.NotFoundError
            If the channel is not found.
        hikari.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.RateLimitedError
            Usually, Hikari will handle and retry on hitting
            rate-limits automatically. This includes most bucket-specific
            rate-limits and global rate-limits. In some rare edge cases,
            however, Discord implements other undocumented rules for
            rate-limiting, such as limits per attribute. These cannot be
            detected or handled normally by Hikari due to their undocumented
            nature, and will trigger this exception if they occur.
        hikari.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
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
        # This will be False if the initial response was deferred with this finishing the referral.
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
        """Edit the last response for this context.

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
        attachment
            A singular attachment to edit the last response with.
        attachments
            A sequence of attachments to edit the last response with.
        component
            If provided, builder object of the component to set for this message.
            This component will replace any previously set components and passing
            [None][] will remove all components.
        components
            If provided, a sequence of the component builder objects set for
            this message. These components will replace any previously set
            components and passing [None][] or an empty sequence will
            remove all components.
        embed
            An embed to replace the last response with.
        embeds
            A sequence of embeds to replace the last response with.
        replace_attachments
            Whether to replace the attachments of the response or not.
        mentions_everyone
            If provided, whether the message should parse @everyone/@here
            mentions.
        user_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake][], or [hikari.users.PartialUser][]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake][], or [hikari.guilds.PartialRole][]
            derivatives to enforce mentioning specific roles.

        Returns
        -------
        hikari.Message
            The message that has been edited.

        Raises
        ------
        ValueError
            If more than 100 unique objects/entities are passed for
            `role_mentions` or `user_mentions`.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        hikari.BadRequestError
            This may be raised in several discrete situations, such as messages
            being empty with no attachments or embeds; messages with more than
            2000 characters in them, embeds that exceed one of the many embed
            limits; too many attachments; attachments that are too large;
            invalid image URLs in embeds; too many components.
        hikari.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.ForbiddenError
            If you are missing the `SEND_MESSAGES` in the channel or the
            person you are trying to message has the DM's disabled.
        hikari.NotFoundError
            If the channel is not found.
        hikari.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.RateLimitedError
            Usually, Hikari will handle and retry on hitting
            rate-limits automatically. This includes most bucket-specific
            rate-limits and global rate-limits. In some rare edge cases,
            however, Discord implements other undocumented rules for
            rate-limiting, such as limits per attribute. These cannot be
            detected or handled normally by Hikari due to their undocumented
            nature, and will trigger this exception if they occur.
        hikari.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
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

        if self._has_responded or self._has_been_deferred:
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
    ) -> typing.Optional[hikari.Message]:
        ...

    @typing.overload
    async def respond(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        ensure_result: typing.Literal[True],
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
    ) -> hikari.Message:
        ...

    async def respond(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        ensure_result: bool = False,
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
    ) -> typing.Optional[hikari.Message]:
        """Respond to this context.

        Parameters
        ----------
        content
            The content to respond with.

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
        ensure_result
            Ensure that this call will always return a message object.

            If [True][] then this will always return [hikari.messages.Message][],
            otherwise this will return `hikari.Message | None`.

            It's worth noting that, under certain scenarios within the slash
            command flow, this may lead to an extre request being made.
        attachment
            If provided, the message attachment. This can be a resource,
            or string of a path on your computer or a URL.
        attachments
            If provided, the message attachments. These can be resources, or
            strings consisting of paths on your computer or URLs.
        component
            If provided, builder object of the component to include in this response.
        components
            If provided, a sequence of the component builder objects to include
            in this response.
        embed
            An embed to respond with.
        embeds
            A sequence of embeds to respond with.
        mentions_everyone
            If provided, whether the message should parse @everyone/@here
            mentions.
        user_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake][], or [hikari.users.PartialUser][]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.snowflakes.Snowflake][], or [hikari.guilds.PartialRole][]
            derivatives to enforce mentioning specific roles.

        Returns
        -------
        hikari.Message | None
            The message that has been created if it was immedieatly available or
            `ensure_result` was set to [True][], else [None][].

        Raises
        ------
        ValueError
            If more than 100 unique objects/entities are passed for
            `role_mentions` or `user_mentions`.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        hikari.BadRequestError
            This may be raised in several discrete situations, such as messages
            being empty with no attachments or embeds; messages with more than
            2000 characters in them, embeds that exceed one of the many embed
            limits; too many attachments; attachments that are too large;
            invalid image URLs in embeds; too many components.
        hikari.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.ForbiddenError
            If you are missing the `SEND_MESSAGES` in the channel or the
            person you are trying to message has the DM's disabled.
        hikari.NotFoundError
            If the channel is not found.
        hikari.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.RateLimitedError
            Usually, Hikari will handle and retry on hitting
            rate-limits automatically. This includes most bucket-specific
            rate-limits and global rate-limits. In some rare edge cases,
            however, Discord implements other undocumented rules for
            rate-limiting, such as limits per attribute. These cannot be
            detected or handled normally by Hikari due to their undocumented
            nature, and will trigger this exception if they occur.
        hikari.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        async with self._response_lock:
            if self._has_responded:
                message = await self._interaction.execute(
                    content,
                    attachment=attachment,
                    attachments=attachments,
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
                    attachment=attachment,
                    attachments=attachments,
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
                attachment=attachment,
                attachments=attachments,
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


_ATTACHMENT_TYPES: tuple[type[typing.Any], ...] = (hikari.files.Resource, *hikari.files.RAWISH_TYPES, os.PathLike)


def _to_list(
    singular: hikari.UndefinedOr[_T],
    plural: hikari.UndefinedOr[typing.Sequence[_T]],
    other: typing.Any,
    type_: typing.Union[type[typing.Any], tuple[type[typing.Any], ...]],
    name: str,
) -> list[_T]:
    if singular is not hikari.UNDEFINED and plural is not hikari.UNDEFINED:
        raise ValueError(f"Only one of {name} or {name}s may be passed")

    if singular:
        return [singular]

    if plural:
        return list(plural)

    if other and isinstance(other, type_):
        return [other]

    return []


class ExecutorClosed(Exception):
    """Error used to indicate that an executor is now closed during execution."""


class ComponentClient:
    """Client used to handle component executors within a REST or gateway flow."""

    __slots__ = ("_constant_ids", "_event_manager", "_executors", "_gc_task", "_prefix_ids", "_server")

    def __init__(
        self,
        *,
        event_manager: typing.Optional[hikari.api.EventManager] = None,
        event_managed: typing.Optional[bool] = None,
        server: typing.Optional[hikari.api.InteractionServer] = None,
    ) -> None:
        """Initialise a component client.

        !!! note
            For an easier way to initialise the client from a bot see
            [yuyo.components.ComponentClient.from_gateway_bot][] and
            [yuyo.components.ComponentClient.from_rest_bot][].

        Parameters
        ----------
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
        self._constant_ids: typing.Dict[str, CallbackSig] = {}
        self._event_manager = event_manager
        self._executors: typing.Dict[int, AbstractComponentExecutor] = {}
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._prefix_ids: typing.Dict[str, CallbackSig] = {}
        self._server = server

        if event_managed or event_managed is None and event_manager:
            if not event_manager:
                raise ValueError("event_managed may only be passed when an event_manager is also passed")

            event_manager.subscribe(hikari.StartingEvent, self._on_starting)
            event_manager.subscribe(hikari.StoppingEvent, self._on_stopping)

    def __enter__(self) -> None:
        self.open()

    def __exit__(
        self,
        exc_type: typing.Optional[type[BaseException]],
        exc: typing.Optional[BaseException],
        exc_traceback: typing.Optional[types.TracebackType],
    ) -> None:
        self.close()

    @classmethod
    def from_gateway_bot(cls, bot: hikari.GatewayBotAware, /, *, event_managed: bool = True) -> ComponentClient:
        """Build a component client froma Gateway Bot.

        Parameters
        ----------
        bot
            The Gateway bot this component client should be bound to.
        event_managed
            Whether the component client should be automatically opened and
            closed based on the lifetime events dispatched by `bot`.

        Returns
        -------
        ComponentClient
            The initialised component client.
        """
        return cls(event_manager=bot.event_manager, event_managed=event_managed)

    @classmethod
    def from_rest_bot(cls, bot: hikari.RESTBotAware, /) -> ComponentClient:
        """Build a component client froma REST Bot.

        Parameters
        ----------
        bot
            The REST bot this component client should be bound to.

        Returns
        -------
        ComponentClient
            The initialised component client.
        """
        return cls(server=bot.interaction_server)

    async def _on_starting(self, event: hikari.StartingEvent) -> None:
        self.open()

    async def _on_stopping(self, event: hikari.StoppingEvent) -> None:
        self.close()

    async def _gc(self) -> None:
        while True:
            for message_id, executor in tuple(self._executors.items()):
                if not executor.has_expired or message_id not in self._executors:
                    continue

                del self._executors[message_id]
                # This may slow this gc task down but the more we yield the better.
                # await executor.close()  # TODO: this

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

        # executor = self._executors
        self._executors = {}
        # for executor in executor.values():  # TODO: finish
        #     executor.close()

    def open(self) -> None:
        """Startup the component client."""
        if self._gc_task:
            return

        self._gc_task = asyncio.get_running_loop().create_task(self._gc())

        if self._server:
            self._server.set_listener(hikari.ComponentInteraction, self.on_rest_request)

        if self._event_manager:
            self._event_manager.subscribe(hikari.InteractionCreateEvent, self.on_gateway_event)

    def _match_constant_id(self, custom_id: str) -> typing.Optional[CallbackSig]:
        return self._constant_ids.get(custom_id) or self._prefix_ids.get(
            next(filter(custom_id.startswith, self._prefix_ids.keys()), "")
        )

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
            self._executors.pop(interaction.message.id, None)

    async def on_gateway_event(self, event: hikari.InteractionCreateEvent, /) -> None:
        if not isinstance(event.interaction, hikari.ComponentInteraction):
            return

        if constant_callback := self._match_constant_id(event.interaction.custom_id):
            await constant_callback(ComponentContext(ephemeral_default=False, interaction=event.interaction))

        elif executor := self._executors.get(event.interaction.message.id):
            await self._execute_executor(executor, event.interaction)

        else:
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE, "This message has timed-out.", flags=hikari.MessageFlag.EPHEMERAL
            )

    async def on_rest_request(self, interaction: hikari.ComponentInteraction, /) -> ResponseT:
        if constant_callback := self._match_constant_id(interaction.custom_id):
            future: asyncio.Future[ResponseT] = asyncio.Future()
            asyncio.create_task(
                constant_callback(
                    ComponentContext(ephemeral_default=False, interaction=interaction, response_future=future)
                )
            )
            return await future

        if executor := self._executors.get(interaction.message.id):
            if not executor.has_expired:
                future = asyncio.Future()
                asyncio.create_task(self._execute_executor(executor, interaction, future=future))
                return await future

            del self._executors[interaction.message.id]

        return (
            interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
            .set_content("This message has timed-out.")
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    def set_constant_id(
        self: _ComponentClientT, custom_id: str, callback: CallbackSig, /, *, prefix_match: bool = False
    ) -> _ComponentClientT:
        """Add a constant "custom_id" callback.

        These are callbacks which'll always be called for a specific custom_id
        while taking priority over executors.

        Parameters
        ----------
        custom_id
            The custom_id to register the callback for.
        callback
            The callback to register.

            This should take a single argument of type [yuyo.components.ComponentContext][],
            be asynchronous and return [None][].
        prefix_match
            Whether the custom_id should be treated as a prefix match.

            This allows for further state to be held in the custom id after the
            prefix and is lower priority than normal custom id match.

        Returns
        -------
        Self
            The component client to allow chaining.

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

    def get_constant_id(self, custom_id: str, /) -> typing.Optional[CallbackSig]:
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

    def remove_constant_id(self: _ComponentClientT, custom_id: str, /) -> _ComponentClientT:
        """Remove a constant "custom_id" callback.

        Parameters
        ----------
        custom_id
            The custom_id to remove the callback for.

        Returns
        -------
        Self
            The component client to allow chaining.

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

    def with_constant_id(
        self, custom_id: str, /, *, prefix_match: bool = False
    ) -> typing.Callable[[CallbackSigT], CallbackSigT]:
        """Add a constant "custom_id" callback through a decorator call.

        These are callbacks which'll always be called for a specific custom_id
        while taking priority over executors.

        Parameters
        ----------
        custom_id
            The custom_id to register the callback for.
        prefix_match
            Whether the custom_id should be treated as a prefix match.

            This allows for further state to be held in the custom id after the
            prefix and is lower priority than normal custom id match.

        Returns
        -------
        Callable[[CallbackSigT], CallbackSigT]
            A decorator to register the callback.

        Raises
        ------
        KeyError
            If the custom_id is already registered.
        """

        def decorator(callback: CallbackSigT, /) -> CallbackSigT:
            self.set_constant_id(custom_id, callback, prefix_match=prefix_match)
            return callback

        return decorator

    def add_executor(
        self: _ComponentClientT, message: hikari.SnowflakeishOr[hikari.Message], executor: AbstractComponentExecutor, /
    ) -> _ComponentClientT:
        """Deprecated alias of [yuyo.components.ComponentClient.add_executor][]."""
        warnings.warn("add_executor is deprecated, use set_executor instead.", DeprecationWarning, stacklevel=2)
        return self.set_executor(message, executor)

    def set_executor(
        self: _ComponentClientT, message: hikari.SnowflakeishOr[hikari.Message], executor: AbstractComponentExecutor, /
    ) -> _ComponentClientT:
        """Set the component executor for a message.

        Parameters
        ----------
        message
            The message to set the executor for.
        executor
            The executor to set.

            This will be called for every component interaction for the message
            unless the component's custom_id is registered as a constant id callback.

        Returns
        -------
        Self
            The component client to allow chaining.
        """
        self._executors[int(message)] = executor
        return self

    def get_executor(
        self, message: hikari.SnowflakeishOr[hikari.Message], /
    ) -> typing.Optional[AbstractComponentExecutor]:
        """Get the component executor set for a message.

        Parameters
        ----------
        message
            The message to get the executor for.

        Returns
        -------
        yuyo.components.AbstractComponentExecutor | None
            The executor set for the message or [None][] if none is set.
        """
        return self._executors.get(int(message))

    def remove_executor(
        self: _ComponentClientT, message: hikari.SnowflakeishOr[hikari.Message], /
    ) -> _ComponentClientT:
        """Remove the component executor for a message.

        Parameters
        ----------
        message
            The message to remove the executor for.

        Returns
        -------
        Self
            The component client to allow chaining.
        """
        self._executors.pop(int(message))
        return self


def as_component_callback(custom_id: str, /) -> typing.Callable[[CallbackSigT], CallbackSigT]:  # noqa: D103
    def decorator(callback: CallbackSigT, /) -> CallbackSigT:
        callback.__custom_id__ = custom_id  # type: ignore
        return callback

    return decorator


class AbstractComponentExecutor(abc.ABC):
    """Abstract interface of an object which handles the execution of a message component."""

    __slots__ = ()

    @property
    @abc.abstractmethod
    def custom_ids(self) -> typing.Collection[str]:
        """Collection of the custom IDs this executor is listening for."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def has_expired(self) -> bool:
        """Whether this executor has ended."""

    @abc.abstractmethod
    async def execute(
        self, _: hikari.ComponentInteraction, /, *, future: typing.Optional[asyncio.Future[ResponseT]] = None
    ) -> None:
        raise NotImplementedError


class ComponentExecutor(AbstractComponentExecutor):  # TODO: Not found action?
    """Basic implementation of a class used for handling the execution of a message component."""

    __slots__ = ("_ephemeral_default", "_id_to_callback", "_last_triggered", "_timeout")

    def __init__(
        self,
        *,
        ephemeral_default: bool = False,
        load_from_attributes: bool = True,
        timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    ) -> None:
        """Initialise a component executor.

        Parameters
        ----------
        ephemeral_default
            Whether this executor's responses should default to being ephemeral.
        timeout
            How long this component should last until its marked as timed out.
        """
        self._ephemeral_default = ephemeral_default
        self._id_to_callback: dict[str, CallbackSig] = {}
        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
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
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._id_to_callback.keys()

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._timeout < datetime.datetime.now(tz=datetime.timezone.utc) - self._last_triggered

    async def execute(
        self, interaction: hikari.ComponentInteraction, /, *, future: typing.Optional[asyncio.Future[ResponseT]] = None
    ) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        ctx = ComponentContext(
            ephemeral_default=self._ephemeral_default, interaction=interaction, response_future=future
        )
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


async def _pre_execution_error(
    interaction: hikari.ComponentInteraction, future: typing.Optional[asyncio.Future[ResponseT]], message: str, /
) -> None:
    if future:
        future.set_result(
            interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
            .set_content(message)
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    else:
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE, message, flags=hikari.MessageFlag.EPHEMERAL
        )


class WaitForExecutor(AbstractComponentExecutor):
    """Component executor used to wait for a single component interaction.

    Examples
    --------
    ```py
    responses: dict[str, str]
    message = await ctx.respond("hi, pick an option", components=[...])
    executor = yuyo.components.WaitFor(authors=(ctx.author.id,), timeout=datetime.timedelta(seconds=30))
    component_client.set_executor(message.id, executor)

    try:
        result = await executor.wait_for()
    except asyncio.TimeoutError:
        await ctx.respond("timed out")

    else:
        await result.respond(responses[result.interaction.custom_id])
    ```
    """

    __slots__ = ("_authors", "_ephemeral_default", "_finished", "_future", "_made_at", "_timeout")

    def __init__(
        self,
        *,
        authors: typing.Optional[typing.Iterable[hikari.SnowflakeishOr[hikari.User]]],
        ephemeral_default: bool = False,
        timeout: datetime.timedelta,
    ) -> None:
        """Initialise a wait for executor.

        Parameters
        ----------
        authors
            The authors of the entries.

            If [None][] is passed here then the paginator will be public (meaning that
            anybody can use it).
        ephemeral_default
            Whether or not the responses made on contexts spawned from this paginator
            should default to ephemeral (meaning only the author can see them) unless
            `flags` is specified on the response method.
        timeout
            How long this should wait for a matching component interaction until it times-out.
        """
        self._authors = set(map(hikari.Snowflake, authors)) if authors else None
        self._ephemeral_default = ephemeral_default
        self._finished = False
        self._future: typing.Optional[asyncio.Future[ComponentContext]] = None
        self._made_at: typing.Optional[datetime.datetime] = None
        self._timeout = timeout

    @property
    def custom_ids(self) -> typing.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return []

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return bool(
            self._finished
            or self._made_at
            and self._timeout < datetime.datetime.now(tz=datetime.timezone.utc) - self._made_at
        )

    async def wait_for(self) -> ComponentContext:
        """Wait for the next matching interaction.

        Returns
        -------
        ComponentContext
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

        self._made_at = datetime.datetime.now(tz=datetime.timezone.utc)
        self._future = asyncio.get_running_loop().create_future()
        try:
            return await asyncio.wait_for(self._future, self._timeout.total_seconds())

        finally:
            self._finished = True

    async def execute(
        self, interaction: hikari.ComponentInteraction, /, *, future: typing.Optional[asyncio.Future[ResponseT]] = None
    ) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        if not self._future:
            await _pre_execution_error(interaction, future, "This button isn't active")
            return

        if self._finished:
            raise ExecutorClosed

        if self._authors and interaction.user.id not in self._authors:
            await _pre_execution_error(interaction, future, "You are not allowed to use this button")
            return

        self._finished = True
        self._future.set_result(
            ComponentContext(interaction=interaction, response_future=future, ephemeral_default=self._ephemeral_default)
        )


WaitForComponent = WaitForExecutor

WaitFor = WaitForExecutor
"""Alias of [yuyo.components.WaitForExecutor][]."""


class InteractiveButtonBuilder(hikari.impl.InteractiveButtonBuilder[ContainerProtoT]):  # noqa: D101
    __slots__ = ("_callback",)

    def __init__(
        self, callback: CallbackSig, container: ContainerProtoT, custom_id: str, style: hikari.ButtonStyle
    ) -> None:
        self._callback = callback
        # pyright doesn't support attrs _ kwargs
        super().__init__(
            container=container, custom_id=custom_id, style=style  # pyright: ignore reportGeneralTypeIssues
        )

    @property
    def callback(self) -> CallbackSig:
        return self._callback

    def add_to_container(self) -> ContainerProtoT:
        self._container.add_callback(self.custom_id, self.callback)
        return super().add_to_container()


class SelectMenuBuilder(hikari.impl.SelectMenuBuilder[ContainerProtoT]):  # noqa: D101
    __slots__ = ("_callback",)

    def __init__(self, callback: CallbackSig, container: ContainerProtoT, custom_id: str) -> None:
        self._callback = callback
        # pyright doesn't support attrs _ kwargs
        super().__init__(container=container, custom_id=custom_id)  # pyright: ignore reportGeneralTypeIssues

    @property
    def callback(self) -> CallbackSig:
        return self._callback

    def add_to_container(self) -> ContainerProtoT:
        self._container.add_callback(self.custom_id, self.callback)
        return super().add_to_container()


class ActionRowExecutor(ComponentExecutor, hikari.api.ComponentBuilder):
    """Class used for handling the execution of an action row."""

    __slots__ = ("_components", "_stored_type")

    def __init__(
        self,
        *,
        ephemeral_default: bool = False,
        load_from_attributes: bool = False,
        timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    ) -> None:
        """Initialise an action row executor.

        Parameters
        ----------
        ephemeral_default
            Whether this executor's responses should default to being ephemeral.
        timeout
            How long this component should last until its marked as timed out.
        """
        super().__init__(
            ephemeral_default=ephemeral_default, load_from_attributes=load_from_attributes, timeout=timeout
        )
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
        style: typing.Literal[hikari.ButtonStyle.LINK, 5],
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

            if isinstance(callback_or_url, str):
                raise ValueError(f"Callback must be passed for an interactive button, not {type(callback_or_url)}")

            return InteractiveButtonBuilder(
                callback=callback_or_url, container=self, style=hikari.ButtonStyle(style), custom_id=custom_id
            )

        # Pyright doesn't properly support _ attrs kwargs
        if not isinstance(callback_or_url, str):
            raise ValueError(f"String url must be passed for Link style buttons, not {type(callback_or_url)}")

        return hikari.impl.LinkButtonBuilder(
            container=self, style=style, url=callback_or_url  # pyright: ignore reportGeneralTypeIssues
        )

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
    """Extended action row implementation which can be tied to a multi-component executor."""

    __slots__ = ("_parent",)

    def __init__(
        self, parent: ParentExecutorProtoT, *, ephemeral_default: bool = False, load_from_attributes: bool = False
    ) -> None:
        super().__init__(ephemeral_default=ephemeral_default, load_from_attributes=load_from_attributes)
        self._parent = parent

    def add_to_parent(self) -> ParentExecutorProtoT:
        """Add this action row to its parent executor.

        Returns
        -------
        ParentExecutorProtoT
            The parent executor this action row was added to.
        """
        return self._parent.add_executor(self).add_builder(self)


def as_child_executor(  # noqa: D103
    executor: typing.Type[AbstractComponentExecutorT], /
) -> typing.Type[AbstractComponentExecutorT]:
    executor.__is_child_executor__ = True  # type: ignore
    return executor


class MultiComponentExecutor(AbstractComponentExecutor):
    """Multi-component implementation of a component executor.

    This implementation allows for multiple components to be executed as a single
    view.
    """

    __slots__ = ("_builders", "_executors", "_last_triggered", "_lock", "_timeout")

    def __init__(
        self,
        *,
        load_from_attributes: bool = False,
        timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    ) -> None:
        """Initialise a multi-component executor.

        Parameters
        ----------
        timeout
            The amount of time to wait after the component's last execution or creation
            until it times out.
        """
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
    def builders(self) -> typing.Sequence[hikari.api.ComponentBuilder]:
        """Sequence of the component builders within this executor."""
        return self._builders

    @property
    def custom_ids(self) -> typing.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return list(itertools.chain.from_iterable(component.custom_ids for component in self._executors))

    @property
    def executors(self) -> typing.Sequence[AbstractComponentExecutor]:
        """Sequence of the child executors within this multi-executor."""
        return self._executors.copy()

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._timeout < datetime.datetime.now(tz=datetime.timezone.utc) - self._last_triggered

    def add_builder(
        self: _MultiComponentExecutorT, builder: hikari.api.ComponentBuilder, /
    ) -> _MultiComponentExecutorT:
        """Add a non-executable component builder to this executor.

        This is useful for adding components that are not meant to be executed, such as a
        a row of link buttons.

        Parameters
        ----------
        builder
            The component builder to add.

        Returns
        -------
        Self
        """
        self._builders.append(builder)
        return self

    def add_action_row(self: _MultiComponentExecutorT) -> ChildActionRowExecutor[_MultiComponentExecutorT]:
        """Create a builder class to add an action row to this executor.

        For the most part this follows the same implementation as
        [yuyo.components.ActionRowExecutor][] except with the added detail that
        [yuyo.components.ChildActionRowExecutor.add_to_parent][] must be called
        to add the action row to the parent executor.

        Returns
        -------
        ChildActionRowExecutor[_MultiComponentExecutorT]
            A builder class to add an action row to this executor.

            [yuyo.components.ChildActionRowExecutor.add_to_parent][] should be
            called to finalise the action row and will return the parent executor
            for chained calls.
        """
        return ChildActionRowExecutor(self)

    def add_executor(
        self: _MultiComponentExecutorT, executor: AbstractComponentExecutor, /
    ) -> _MultiComponentExecutorT:
        """Add a component executor to this multi-component executor.

        This method is internally used by the `add_{component}` methods.

        Parameters
        ----------
        executor
            The component executor to add.

        Returns
        -------
        Self
            The multi-component executor instance to enable chained calls.
        """
        self._executors.append(executor)
        return self

    async def execute(
        self, interaction: hikari.ComponentInteraction, /, *, future: typing.Optional[asyncio.Future[ResponseT]] = None
    ) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        for executor in self._executors:
            if interaction.custom_id in executor.custom_ids:
                await executor.execute(interaction, future=future)
                return

        raise KeyError("Custom ID not found")  # TODO: do we want to respond here?


class ComponentPaginator(ActionRowExecutor):
    """Standard implementation of an action row executor used for pagination.

    This is a convenience class that allows you to easily implement a paginator.
    """

    __slots__ = ("_authors", "_buffer", "_index", "_iterator", "_lock")

    def __init__(
        self,
        iterator: pagination.IteratorT[pagination.EntryT],
        *,
        authors: typing.Optional[typing.Iterable[hikari.SnowflakeishOr[hikari.User]]],
        ephemeral_default: bool = False,
        triggers: typing.Collection[str] = (
            pagination.LEFT_TRIANGLE,
            pagination.STOP_SQUARE,
            pagination.RIGHT_TRIANGLE,
        ),
        load_from_attributes: bool = False,
        timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    ) -> None:
        """Initialise a component paginator.

        Parameters
        ----------
        iterator
            The iterator to paginate.

            This should be an iterator of tuples of `(hikari.UndefinedOr[str],
            hikari.UndefinedOr[hikari.Embed])`.
        authors
            The authors of the entries.

            If None is passed here then the paginator will be public (meaning that
            anybody can use it).
        ephemeral_default
            Whether or not the responses made on contexts spawned from this paginator
            should default to ephemeral (meaning only the author can see them) unless
            `flags` is specified on the response method.
        triggers
            Collection of the unicode emojis that should trigger this paginator.

            As of current the only usable emojis are [yuyo.pagination.LEFT_TRIANGLE][],
            [yuyo.pagination.RIGHT_TRIANGLE][], [yuyo.pagination.STOP_SQUARE][],
            [yuyo.pagination.LEFT_DOUBLE_TRIANGLE][] and [yuyo.pagination.LEFT_TRIANGLE][].
        timeout
            The amount of time to wait after the component's last execution or creation
            until it times out.
        """
        if not isinstance(
            iterator, (typing.Iterator, typing.AsyncIterator)
        ):  # pyright: ignore reportUnnecessaryIsInstance
            raise ValueError(f"Invalid value passed for `iterator`, expected an iterator but got {type(iterator)}")

        super().__init__(
            ephemeral_default=ephemeral_default, load_from_attributes=load_from_attributes, timeout=timeout
        )

        self._authors = set(map(hikari.Snowflake, authors)) if authors else None
        self._buffer: typing.List[pagination.EntryT] = []
        self._ephemeral_default = ephemeral_default
        self._index: int = -1
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

    def builder(self) -> typing.Sequence[hikari.api.ComponentBuilder]:
        """Get a sequence of the component builders for this paginator.

        Returns
        -------
        typing.Sequence[hikari.api.ComponentBuilder]
            The component builders for this paginator.
        """
        return [self]

    async def execute(
        self, interaction: hikari.ComponentInteraction, /, *, future: typing.Optional[asyncio.Future[ResponseT]] = None
    ) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        if self._authors and interaction.user.id not in self._authors:
            await _pre_execution_error(interaction, future, "You are not allowed to use this button")
            return

        await super().execute(interaction, future=future)

    async def get_next_entry(self, /) -> typing.Optional[pagination.EntryT]:
        """Get the next entry in this paginator.

        This is generally helpful for making the message which the paginator will be based off
        and will still internally store the entry and increment the position of the paginator.

        Examples
        --------
        ```py
        response_paginator = yuyo.ComponentPaginator(
            pages,
            authors=(ctx.author.id,)
        )
        first_response = await response_paginator.get_next_entry()
        assert first_response
        content, embed = first_response
        message = await ctx.respond(content=content, embed=embed, component=response_paginator, ensure_result=True)
        component_client.set_executor(message, response_paginator)
        ```

        Returns
        -------
        yuyo.pagination.EntryT | None
            The next entry in this paginator, or [None][] if there are no more entries.
        """
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
    def _noop(ctx: ComponentContext) -> typing.Coroutine[typing.Any, typing.Any, None]:
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
        await ctx.defer(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
        await ctx.delete_initial_response()
        raise ExecutorClosed

    async def _on_last(self, ctx: ComponentContext, /) -> None:
        if self._iterator:
            # TODO: option to not lock on last
            loading_component = (
                ctx.interaction.app.rest.build_action_row()
                .add_button(hikari.ButtonStyle.SECONDARY, "loading")
                .set_is_disabled(True)
                .set_emoji(878377505344614461)
                .add_to_container()
            )
            await ctx.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE, component=loading_component)
            self._buffer.extend(await pagination.collect_iterator(self._iterator))
            self._index = len(self._buffer) - 1
            self._iterator = None

            if self._buffer:
                content, embed = self._buffer[self._index]
                await ctx.edit_initial_response(components=self.builder(), content=content, embed=embed)

            else:
                await ctx.edit_initial_response(components=self.builder())

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
