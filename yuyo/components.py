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
"""Higher level client for callback based component execution."""
from __future__ import annotations

__all__: list[str] = [
    "ActionColumnExecutor",
    "ComponentClient",
    "ComponentContext",
    "ComponentExecutor",
    "ComponentPaginator",
    "WaitForExecutor",
    "as_channel_menu",
    "as_interactive_button",
    "as_mentionable_menu",
    "as_role_menu",
    "as_select_menu",
    "as_text_menu",
    "as_user_menu",
    "column_template",
    "link_button",
    "with_option",
]

import abc
import asyncio
import base64
import copy
import datetime
import functools
import hashlib
import itertools
import logging
import os
import types
import typing
from collections import abc as collections

import alluka as alluka_
import hikari
import typing_extensions

from . import _internal
from . import pagination
from . import timeouts

_T = typing.TypeVar("_T")

if typing.TYPE_CHECKING:
    import tanjun
    from typing_extensions import Self

    _OtherT = typing.TypeVar("_OtherT")
    _TextMenuT = typing.TypeVar(
        "_TextMenuT", "_TextMenuDescriptor[typing.Any, typing.Any]", "_WrappedTextMenuBuilder[...]"
    )


_P = typing_extensions.ParamSpec("_P")
_CoroT = collections.Coroutine[typing.Any, typing.Any, None]
_SelfT = typing.TypeVar("_SelfT")
_PartialInteractionT = typing.TypeVar("_PartialInteractionT", hikari.ModalInteraction, hikari.ComponentInteraction)
_INTERACTION_LIFETIME: typing.Final[datetime.timedelta] = datetime.timedelta(minutes=15)

_ComponentResponseT = typing.Union[
    hikari.api.InteractionMessageBuilder, hikari.api.InteractionDeferredBuilder, hikari.api.InteractionModalBuilder
]
"""Type hint of the builder response types allows for component interactions."""

CallbackSig = collections.Callable[..., collections.Coroutine[typing.Any, typing.Any, None]]
"""Type hint of a component callback."""

_CallbackSigT = typing.TypeVar("_CallbackSigT", bound=CallbackSig)

_LOGGER = logging.getLogger("hikari.yuyo.components")


def _delete_after_to_float(delete_after: typing.Union[datetime.timedelta, float, int], /) -> float:
    return delete_after.total_seconds() if isinstance(delete_after, datetime.timedelta) else float(delete_after)


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


class BaseContext(abc.ABC, typing.Generic[_PartialInteractionT]):
    """Base class for components contexts."""

    __slots__ = (
        "_ephemeral_default",
        "_has_responded",
        "_has_been_deferred",
        "_interaction",
        "_id_match",
        "_id_metadata",
        "_last_response_id",
        "_register_task",
        "_response_future",
        "_response_lock",
    )

    def __init__(
        self,
        interaction: _PartialInteractionT,
        id_match: str,
        id_metadata: str,
        register_task: collections.Callable[[asyncio.Task[typing.Any]], None],
        *,
        ephemeral_default: bool = False,
        response_future: typing.Union[
            # _ModalResponseT
            asyncio.Future[typing.Union[hikari.api.InteractionMessageBuilder, hikari.api.InteractionDeferredBuilder]],
            asyncio.Future[_ComponentResponseT],
            None,
        ] = None,
    ) -> None:
        self._ephemeral_default = ephemeral_default
        self._has_responded = False
        self._has_been_deferred = False
        self._id_match = id_match
        self._id_metadata = id_metadata
        self._interaction: _PartialInteractionT = interaction
        self._last_response_id: typing.Optional[hikari.Snowflake] = None
        self._register_task = register_task
        self._response_future = response_future
        self._response_lock = asyncio.Lock()

    @property
    def id_match(self) -> str:
        """Section of the ID used to identify the relevant executor."""
        return self._id_match

    @property
    def id_metadata(self) -> str:
        """Metadata from the interaction's custom ID."""
        return self._id_metadata

    @property
    def expires_at(self) -> datetime.datetime:
        """When this application command context expires.

        After this time is reached, the message/response methods on this
        context will always raise [hikari.errors.NotFoundError][].
        """
        return self._interaction.created_at + _INTERACTION_LIFETIME

    @property
    def has_been_deferred(self) -> bool:
        """Whether this context's initial response has been deferred.

        This will be true if [yuyo.components.BaseContext.defer][] has been called.
        """
        return self._has_been_deferred

    @property
    def has_responded(self) -> bool:
        """Whether an initial response has been made to this context yet.

        It's worth noting that a context must be either responded to or
        deferred within 3 seconds from it being received otherwise it'll be
        marked as failed.

        This will be true if either [yuyo.components.BaseContext.respond][],
        [yuyo.components.BaseContext.create_initial_response][] or
        [yuyo.components.BaseContext.edit_initial_response][]
        (after a deferral) has been called.
        """
        return self._has_responded

    @property
    def interaction(self) -> _PartialInteractionT:
        """Object of the interaction this context is for."""
        return self._interaction

    def set_ephemeral_default(self, state: bool, /) -> Self:
        """Set the ephemeral default state for this context.

        Parameters
        ----------
        state
            The new ephemeral default state.

            If this is [True][] then all calls to the response creating methods
            on this context will default to being ephemeral.
        """
        self._ephemeral_default = state
        return self

    def _validate_delete_after(self, delete_after: typing.Union[float, int, datetime.timedelta], /) -> float:
        delete_after = _delete_after_to_float(delete_after)
        time_left = (
            _INTERACTION_LIFETIME - (datetime.datetime.now(tz=datetime.timezone.utc) - self._interaction.created_at)
        ).total_seconds()
        if delete_after + 10 > time_left:
            raise ValueError("This interaction will have expired before delete_after is reached")

        return delete_after

    def _get_flags(self, flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag], /) -> int:
        if flags is not hikari.UNDEFINED:
            assert isinstance(flags, int)
            return flags

        return hikari.MessageFlag.EPHEMERAL if self._ephemeral_default else hikari.MessageFlag.NONE

    @abc.abstractmethod
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

    async def _delete_followup_after(self, delete_after: float, message: hikari.Message, /) -> None:
        await asyncio.sleep(delete_after)
        try:
            await self._interaction.delete_message(message)
        except hikari.NotFoundError as exc:
            _LOGGER.debug("Failed to delete response message after %.2f seconds", delete_after, exc_info=exc)

    async def _create_followup(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
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
        tts: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag] = hikari.UNDEFINED,
    ) -> hikari.Message:
        delete_after = self._validate_delete_after(delete_after) if delete_after is not None else None
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
        # This behaviour is undocumented and only kept by Discord for "backwards compatibility"
        # but the followup endpoint can be used to create the initial response for slash
        # commands or edit in a deferred response and (while this does lead to some
        # unexpected behaviour around deferrals) should be accounted for.
        self._has_responded = True

        if delete_after is not None:
            self._register_task(asyncio.create_task(self._delete_followup_after(delete_after, message)))

        return message

    async def create_followup(
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
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Slash command responses can only be deleted within 15 minutes of the
            command being received.
        ephemeral
            Whether the deferred response should be ephemeral.
            Passing [True][] here is a shorthand for including `1 << 64` in the
            passed flags.
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

            If the interaction will have expired before `delete_after` is reached.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        """
        if ephemeral:
            flags = (flags or hikari.MessageFlag.NONE) | hikari.MessageFlag.EPHEMERAL

        async with self._response_lock:
            return await self._create_followup(
                content=content,
                delete_after=delete_after,
                attachment=attachment,
                attachments=attachments,
                component=component,
                components=components,
                embed=embed,
                embeds=embeds,
                mentions_everyone=mentions_everyone,
                user_mentions=user_mentions,
                role_mentions=role_mentions,
                tts=tts,
                flags=flags,
            )

    async def _delete_initial_response_after(self, delete_after: float, /) -> None:
        await asyncio.sleep(delete_after)
        try:
            await self.delete_initial_response()
        except hikari.NotFoundError as exc:
            _LOGGER.debug("Failed to delete response message after %.2f seconds", delete_after, exc_info=exc)

    async def _create_initial_response(
        self,
        response_type: hikari.MessageResponseTypesT,
        /,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
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
        flags = self._get_flags(flags)
        delete_after = self._validate_delete_after(delete_after) if delete_after is not None else None
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
            attachments, content = _to_list(attachment, attachments, content, _ATTACHMENT_TYPES, "attachment")
            components, content = _to_list(component, components, content, hikari.api.ComponentBuilder, "component")
            embeds, content = _to_list(embed, embeds, content, hikari.Embed, "embed")

            content = str(content) if content is not hikari.UNDEFINED else hikari.UNDEFINED
            result = hikari.impl.InteractionMessageBuilder(
                response_type,
                content,
                attachments=attachments,
                components=components,
                embeds=embeds,
                flags=flags,
                is_tts=tts,
                mentions_everyone=mentions_everyone,
                user_mentions=user_mentions,
                role_mentions=role_mentions,
            )

            self._response_future.set_result(result)

        self._has_responded = True
        if delete_after is not None:
            self._register_task(asyncio.create_task(self._delete_initial_response_after(delete_after)))

    @abc.abstractmethod
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
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
        attachment: hikari.UndefinedNoneOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedNoneOr[collections.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        component: hikari.UndefinedNoneOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedNoneOr[collections.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedNoneOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedNoneOr[collections.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: typing.Union[
            hikari.SnowflakeishSequence[hikari.PartialUser], bool, hikari.UndefinedType
        ] = hikari.UNDEFINED,
        role_mentions: typing.Union[
            hikari.SnowflakeishSequence[hikari.PartialRole], bool, hikari.UndefinedType
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
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Slash command responses can only be deleted within 15 minutes of
            the command being received.
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

            If `delete_after` would be more than 15 minutes after the slash
            command was called.

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
        hikari.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        delete_after = self._validate_delete_after(delete_after) if delete_after is not None else None
        message = await self._interaction.edit_initial_response(
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
        )
        # This will be False if the initial response was deferred with this finishing the referral.
        self._has_responded = True

        if delete_after is not None:
            self._register_task(asyncio.create_task(self._delete_initial_response_after(delete_after)))

        return message

    async def edit_last_response(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
        attachment: hikari.UndefinedNoneOr[hikari.Resourceish] = hikari.UNDEFINED,
        attachments: hikari.UndefinedNoneOr[collections.Sequence[hikari.Resourceish]] = hikari.UNDEFINED,
        component: hikari.UndefinedNoneOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedNoneOr[collections.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
        embed: hikari.UndefinedNoneOr[hikari.Embed] = hikari.UNDEFINED,
        embeds: hikari.UndefinedNoneOr[collections.Sequence[hikari.Embed]] = hikari.UNDEFINED,
        mentions_everyone: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        user_mentions: typing.Union[
            hikari.SnowflakeishSequence[hikari.PartialUser], bool, hikari.UndefinedType
        ] = hikari.UNDEFINED,
        role_mentions: typing.Union[
            hikari.SnowflakeishSequence[hikari.PartialRole], bool, hikari.UndefinedType
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
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Slash command responses can only be deleted within 15 minutes of
            the command being received.
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

            If `delete_after` would be more than 15 minutes after the slash
            command was called.

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
        hikari.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        if self._last_response_id:
            delete_after = self._validate_delete_after(delete_after) if delete_after is not None else None
            message = await self._interaction.edit_message(
                self._last_response_id,
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
            )
            if delete_after is not None:
                self._register_task(asyncio.create_task(self._delete_followup_after(delete_after, message)))

            return message

        if self._has_responded or self._has_been_deferred:
            return await self.edit_initial_response(
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
            )

        raise LookupError("Context has no previous responses")

    async def fetch_initial_response(self) -> hikari.Message:
        """Fetch the initial response for this context.

        Returns
        -------
        hikari.messages.Message
            The initial response's message object.

        Raises
        ------
        LookupError, hikari.NotFoundError
            The response was not found.
        """
        return await self._interaction.fetch_initial_response()

    async def fetch_last_response(self) -> hikari.Message:
        """Fetch the last response for this context.

        Returns
        -------
        hikari.messages.Message
            The most response response's message object.

        Raises
        ------
        LookupError, hikari.NotFoundError
            The response was not found.
        """
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
        ensure_result: typing.Literal[True],
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
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
    ) -> hikari.Message:
        ...

    @typing.overload
    async def respond(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        ensure_result: bool = False,
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
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
    ) -> typing.Optional[hikari.Message]:
        ...

    async def respond(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        ensure_result: bool = False,
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
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
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Slash command responses can only be deleted within 15 minutes of
            the command being received.
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

            If `delete_after` would be more than 15 minutes after the slash
            command was called.

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
        hikari.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        async with self._response_lock:
            if self._has_responded:
                return await self._create_followup(
                    content,
                    delete_after=delete_after,
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

            if self._has_been_deferred:
                return await self.edit_initial_response(
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
                )

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
            )

        if ensure_result:
            return await self._interaction.fetch_initial_response()

        return None  # MyPy


class ComponentContext(BaseContext[hikari.ComponentInteraction]):
    """The context used for message component triggers."""

    __slots__ = ("_client",)

    def __init__(
        self,
        client: ComponentClient,
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
    def client(self) -> ComponentClient:
        """The component client this context is bound to."""
        return self._client

    async def create_initial_response(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        response_type: hikari.MessageResponseTypesT = hikari.ResponseType.MESSAGE_CREATE,
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
        response_type
            The type of message response to give.
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
                response_type,
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

    async def create_modal_response(
        self,
        title: str,
        custom_id: str,
        /,
        *,
        component: hikari.UndefinedOr[hikari.api.ComponentBuilder] = hikari.UNDEFINED,
        components: hikari.UndefinedOr[collections.Sequence[hikari.api.ComponentBuilder]] = hikari.UNDEFINED,
    ) -> None:
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
        hikari.BadRequestError
            When the requests' data is outside Discord's accept ranges/validation.
        hikari.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.NotFoundError
            If the interaction is not found or if the interaction's initial
            response has already been created or deferred.
        hikari.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        async with self._response_lock:
            if self._has_responded or self._has_been_deferred:
                raise RuntimeError("Initial response has already been created")

            if self._response_future:
                components, _ = _to_list(component, components, None, hikari.api.ComponentBuilder, "component")

                response = hikari.impl.InteractionModalBuilder(title, custom_id, components or [])
                self._response_future.set_result(response)

            else:
                await self._interaction.create_modal_response(
                    title, custom_id, component=component, components=components
                )

            self._has_responded = True

    async def defer(
        self,
        *,
        defer_type: hikari.DeferredResponseTypesT = hikari.ResponseType.DEFERRED_MESSAGE_CREATE,
        ephemeral: bool = False,
        flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag] = hikari.UNDEFINED,
    ) -> None:
        """Defer the initial response for this context.

        !!! note
            The ephemeral state of the first response is decided by whether the
            deferral is ephemeral.

        Parameters
        ----------
        defer_type
            The type of deferral this should be.

            This may any of the following
            * [ResponseType.DEFERRED_MESSAGE_CREATE][hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_CREATE]
                to indicate that the following up call to
                [yuyo.components.BaseContext.edit_initial_response][]
                or [yuyo.components.BaseContext.respond][] should create
                a new message.
            * [ResponseType.DEFERRED_MESSAGE_UPDATE][hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE]
                to indicate that the following call to the aforementioned
                methods should update the existing message.
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
                self._response_future.set_result(self._interaction.build_deferred_response(defer_type).set_flags(flags))

            else:
                await self._interaction.create_initial_response(defer_type, flags=flags)


Context = ComponentContext
"""Alias of [ComponentContext][yuyo.components.ComponentContext]."""


_ATTACHMENT_TYPES: tuple[type[typing.Any], ...] = (hikari.files.Resource, *hikari.files.RAWISH_TYPES, os.PathLike)


def _to_list(
    singular: hikari.UndefinedOr[_T],
    plural: hikari.UndefinedOr[collections.Sequence[_T]],
    other: _OtherT,
    type_: typing.Union[type[_T], tuple[type[_T], ...]],
    name: str,
    /,
) -> tuple[hikari.UndefinedOr[list[_T]], hikari.UndefinedOr[_OtherT]]:
    if singular is not hikari.UNDEFINED and plural is not hikari.UNDEFINED:
        raise ValueError(f"Only one of {name} or {name}s may be passed")

    if singular is not hikari.UNDEFINED:
        return [singular], other

    if plural is not hikari.UNDEFINED:
        return list(plural), other

    if other and isinstance(other, type_):
        return [other], hikari.UNDEFINED

    return hikari.UNDEFINED, other


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

    __slots__ = ("_alluka", "_event_manager", "_executors", "_gc_task", "_message_executors", "_server", "_tasks")

    def __init__(
        self,
        *,
        alluka: typing.Optional[alluka_.abc.Client] = None,
        event_manager: typing.Optional[hikari.api.EventManager] = None,
        event_managed: typing.Optional[bool] = None,
        server: typing.Optional[hikari.api.InteractionServer] = None,
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
            alluka = alluka_.Client()
            self._set_standard_deps(alluka)

        self._alluka = alluka

        self._executors: dict[str, tuple[timeouts.AbstractTimeout, AbstractComponentExecutor]] = {}
        """Dict of custom IDs to executors."""

        self._event_manager = event_manager
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._message_executors: dict[hikari.Snowflake, tuple[timeouts.AbstractTimeout, AbstractComponentExecutor]] = {}
        """Dict of message IDs to executors."""

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
        client = cls(alluka=alluka, server=bot.interaction_server)

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

        self = cls(alluka=tanjun_client.injector, event_manager=tanjun_client.events, server=tanjun_client.server)
        self._set_standard_deps(tanjun_client.injector)

        if tanjun_managed:
            tanjun_client.add_client_callback(tanjun.ClientCallbackNames.STARTING, self.open)
            tanjun_client.add_client_callback(tanjun.ClientCallbackNames.CLOSING, self.close)

        return self

    def _set_standard_deps(self, alluka: alluka_.abc.Client) -> None:
        alluka.set_type_dependency(ComponentClient, self)

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

        ctx = ComponentContext(
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
        """
        if timeout is _internal.NO_DEFAULT:
            timeout = timeouts.SlidingTimeout(datetime.timedelta(seconds=30), max_uses=-1)

        elif timeout is None:
            timeout = timeouts.NeverTimeout()

        entry = (timeout, executor)

        if message:
            self._message_executors[hikari.Snowflake(message)] = entry

        else:
            for custom_id in executor.custom_ids:
                self._executors[custom_id] = entry

        return self

    def get_executor_for_message(
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
        """
        for custom_id in executor.custom_ids:
            if (entry := self._executors.get(custom_id)) and entry[1] == executor:
                del self._executors[custom_id]

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
        """
        self._message_executors.pop(hikari.Snowflake(message))
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
    async def execute(self, ctx: ComponentContext, /) -> None:
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

    async def execute(self, ctx: ComponentContext, /) -> None:
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

    async def execute(self, ctx: ComponentContext, /) -> None:
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
    message = await ctx.respond("hi, pick an option", components=[...])
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

    __slots__ = ("_authors", "_ephemeral_default", "_finished", "_future", "_timeout", "_timeout_at")

    def __init__(
        self,
        *,
        authors: typing.Optional[collections.Iterable[hikari.SnowflakeishOr[hikari.User]]] = None,
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
        self._timeout = timeout
        self._timeout_at: typing.Optional[datetime.datetime] = None

    @property
    def custom_ids(self) -> collections.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return []

    @property
    def has_expired(self) -> bool:
        return bool(self._finished or self._timeout_at and _now() > self._timeout_at)

    def increment_uses(self) -> bool:
        return True

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

        self._timeout_at = _now() + self._timeout if self._timeout else None
        self._future = asyncio.get_running_loop().create_future()
        try:
            return await asyncio.wait_for(self._future, self._timeout.total_seconds() if self._timeout else None)

        finally:
            self._finished = True

    async def execute(self, ctx: ComponentContext, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        ctx.set_ephemeral_default(self._ephemeral_default)
        if not self._future:
            await ctx.create_initial_response("The bot isn't ready for that yet", ephemeral=True)
            return

        if self._finished:
            raise ExecutorClosed

        if self._authors and ctx.interaction.user.id not in self._authors:
            await ctx.create_initial_response("You are not allowed to use this component", ephemeral=True)
            return

        self._finished = True
        self._future.set_result(ctx)


WaitFor = WaitForExecutor
"""Alias of [yuyo.components.WaitForExecutor][]."""


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
        if isinstance(_mro_type, type) and issubclass(_mro_type, hikari.PartialChannel):
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
    ) -> collections.Callable[typing_extensions.Concatenate[_SelfT, _P], _CoroT]:
        ...

    @typing.overload
    def __get__(
        self, obj: object, obj_type: typing.Optional[type[typing.Any]] = None
    ) -> collections.Callable[_P, _CoroT]:
        ...

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
            self_bound=True,
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
) -> _SelectMenu[_SelfT, _P]:
    ...


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
]:
    ...


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
) -> _SelectMenu[_SelfT, _P]:
    ...


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
]:
    ...


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
) -> _SelectMenu[_SelfT, _P]:
    ...


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
]:
    ...


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
) -> _ChannelSelect[_SelfT, _P]:
    ...


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
]:
    ...


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
) -> _TextMenuDescriptor[_SelfT, _P]:
    ...


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
]:
    ...


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

        These can also be added by using [yuyo.components.with_option][].
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

    async def execute(self, ctx: ComponentContext, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        ctx.set_ephemeral_default(self._ephemeral_default)

        if self._authors and ctx.interaction.user.id not in self._authors:
            await ctx.create_initial_response("You are not allowed to use this component", ephemeral=True)
            return

        callback = self._callbacks[ctx.id_match]
        await ctx.client.alluka.call_with_async_di(callback, ctx)

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_mentionable_menu(self, callback: _CallbackSigT, /) -> _CallbackSigT:
        ...

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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        ...

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_static_mentionable_menu(cls, callback: _CallbackSigT, /) -> _CallbackSigT:
        ...

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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        ...

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_role_menu(self, callback: _CallbackSigT, /) -> _CallbackSigT:
        ...

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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        ...

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_static_role_menu(cls, callback: _CallbackSigT, /) -> _CallbackSigT:
        ...

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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        ...

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_user_menu(self, callback: _CallbackSigT, /) -> _CallbackSigT:
        ...

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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        ...

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_static_user_menu(cls, callback: _CallbackSigT, /) -> _CallbackSigT:
        ...

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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        ...

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_channel_menu(self, callback: _CallbackSigT, /) -> _CallbackSigT:
        ...

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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        ...

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_static_channel_menu(cls, callback: _CallbackSigT, /) -> _CallbackSigT:
        ...

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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        ...

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_text_menu(self, callback: collections.Callable[_P, _CoroT], /) -> _WrappedTextMenuBuilder[_P]:
        ...

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
    ) -> collections.Callable[[collections.Callable[_P, _CoroT]], _WrappedTextMenuBuilder[_P]]:
        ...

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

            These can also be added using [yuyo.components.with_option][].
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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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
    def with_static_text_menu(cls, callback: collections.Callable[_P, _CoroT], /) -> _WrappedTextMenuBuilder[_P]:
        ...

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
    ) -> collections.Callable[[collections.Callable[_P, _CoroT]], _WrappedTextMenuBuilder[_P]]:
        ...

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
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
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

            This should be an iterator of [yuyo.pagination.Page][]s.
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
        [yuyo.components.ComponentPaginator.__init__][ComponentPaginator.\_\_init\_\_]
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
        [yuyo.components.ComponentPaginator.__init__][ComponentPaginator.\_\_init\_\_]
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
        [yuyo.components.ComponentPaginator.__init__][ComponentPaginator.\_\_init\_\_]
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
        [yuyo.components.ComponentPaginator.__init__][ComponentPaginator.\_\_init\_\_]
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
        [yuyo.components.ComponentPaginator.__init__][ComponentPaginator.\_\_init\_\_]
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

    async def execute(self, ctx: ComponentContext, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        ctx.set_ephemeral_default(self._ephemeral_default)
        if self._authors and ctx.interaction.user.id not in self._authors:
            await ctx.create_initial_response("You are not allowed to use this component", ephemeral=True)
            return

        await super().execute(ctx)

    async def get_next_entry(self) -> typing.Optional[pagination.Page]:
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
        yuyo.pagination.Page | None
            The next entry in this paginator, or [None][] if there are no more entries.
        """
        return await self._paginator.step_forward()

    async def _on_first(self, ctx: ComponentContext, /) -> None:
        if page := self._paginator.jump_to_first():
            await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, **page.to_kwargs())

        else:
            await _noop(ctx)

    async def _on_previous(self, ctx: ComponentContext, /) -> None:
        if page := self._paginator.step_back():
            await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, **page.to_kwargs())

        else:
            await _noop(ctx)

    async def _on_disable(self, ctx: ComponentContext, /) -> None:
        self._paginator.close()
        await ctx.defer(defer_type=hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
        await ctx.delete_initial_response()
        raise ExecutorClosed(already_closed=False)

    async def _on_last(self, ctx: ComponentContext, /) -> None:
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

        else:
            await _noop(ctx)

    async def _on_next(self, ctx: ComponentContext, /) -> None:
        if page := await self._paginator.step_forward():
            await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, **page.to_kwargs())

        else:
            await _noop(ctx)


def _noop(ctx: ComponentContext, /) -> _CoroT:
    """Create a noop initial response to a component context."""
    return ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE)


Paginator = ComponentPaginator
"""Alias of [ComponentPaginator][yuyo.components.ComponentPaginator]."""
