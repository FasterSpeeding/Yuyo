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
    "ActionRowExecutor",
    "ComponentClient",
    "ComponentContext",
    "ComponentExecutor",
    "ComponentPaginator",
    "WaitFor",
    "WaitForExecutor",
]

import abc
import asyncio
import datetime
import itertools
import logging
import os
import typing
from collections import abc as collections

import alluka as alluka_
import hikari

from . import _internal
from . import pagination
from . import timeouts

if typing.TYPE_CHECKING:
    import types

    import tanjun
    from typing_extensions import Self

    _T = typing.TypeVar("_T")
    _OtherT = typing.TypeVar("_OtherT")
    _ActionColumnExecutorT = typing.TypeVar("_ActionColumnExecutorT", bound="ActionColumnExecutor")


_ParentT = typing.TypeVar("_ParentT")
_PartialInteractionT = typing.TypeVar("_PartialInteractionT", hikari.ModalInteraction, hikari.ComponentInteraction)
_INTERACTION_LIFETIME: typing.Final[datetime.timedelta] = datetime.timedelta(minutes=15)

CallbackSig = collections.Callable[..., collections.Coroutine[typing.Any, typing.Any, None]]
"""Type hint of a component callback."""

_CallbackSigT = typing.TypeVar("_CallbackSigT", bound=CallbackSig)

_ComponentResponseT = typing.Union[
    hikari.api.InteractionMessageBuilder, hikari.api.InteractionDeferredBuilder, hikari.api.InteractionModalBuilder
]
"""Type hint of the builder response types allows for component interactions."""

_LOGGER = logging.getLogger("hikari.yuyo.components")


def _delete_after_to_float(delete_after: typing.Union[datetime.timedelta, float, int], /) -> float:
    return delete_after.total_seconds() if isinstance(delete_after, datetime.timedelta) else float(delete_after)


def _to_timeout(value: typing.Optional[datetime.timedelta], /) -> timeouts.AbstractTimeout:
    if value is None:
        return timeouts.NeverTimeout()

    return timeouts.BasicTimeout(value, max_uses=-1)


class BaseContext(abc.ABC, typing.Generic[_PartialInteractionT]):
    """Base class for components contexts."""

    __slots__ = (
        "_ephemeral_default",
        "_has_responded",
        "_has_been_deferred",
        "_interaction",
        "_last_response_id",
        "_register_task",
        "_response_future",
        "_response_lock",
    )

    def __init__(
        self,
        interaction: _PartialInteractionT,
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
        self._interaction: _PartialInteractionT = interaction
        self._last_response_id: typing.Optional[hikari.Snowflake] = None
        self._register_task = register_task
        self._response_future = response_future
        self._response_lock = asyncio.Lock()

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
        response_type: hikari.ComponentResponseTypesT,
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
                user_mentions=user_mentions,  # pyright: ignore [ reportGeneralTypeIssues ]  # TODO: fix on hikari
                role_mentions=role_mentions,  # pyright: ignore [ reportGeneralTypeIssues ]  # TODO: fix on hikari
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
        register_task: collections.Callable[[asyncio.Task[typing.Any]], None],
        *,
        ephemeral_default: bool = False,
        response_future: typing.Optional[asyncio.Future[_ComponentResponseT]] = None,
    ) -> None:
        super().__init__(
            interaction, register_task, ephemeral_default=ephemeral_default, response_future=response_future
        )
        self._client = client
        self._response_future = response_future

    @property
    def select_channels(self) -> collections.Mapping[hikari.Snowflake, hikari.InteractionChannel]:
        """Sequence of the users passed for a channel select menu."""
        if not self.interaction.resolved:
            return {}

        return self.interaction.resolved.channels

    @property
    def select_roles(self) -> collections.Mapping[hikari.Snowflake, hikari.Role]:
        """Sequence of the users passed for a role select menu.

        This will also include some of the values for a mentionable select menu.
        """
        if not self.interaction.resolved:
            return {}

        return self.interaction.resolved.roles

    @property
    def select_texts(self) -> collections.Sequence[str]:
        """Sequence of the values passed for a text select menu."""
        return self._interaction.values

    @property
    def select_users(self) -> collections.Mapping[hikari.Snowflake, hikari.User]:
        """Sequence of the users passed for a user select menu.

        This will also include some of the values for a mentionable select menu.

        [ComponentContext.select_members][yuyo.components.ComponentContext.select_members]
        has the full member objects.
        """
        if not self.interaction.resolved:
            return {}

        return self.interaction.resolved.users

    @property
    def select_members(self) -> collections.Mapping[hikari.Snowflake, hikari.InteractionMember]:
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


class ExecutorClosed(Exception):
    """Error used to indicate that an executor is now closed during execution."""


class ComponentClient:
    """Client used to handle component executors within a REST or gateway flow."""

    __slots__ = (
        "_alluka",
        "_constant_ids",
        "_event_manager",
        "_executors",
        "_gc_task",
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
        self._constant_ids: dict[str, CallbackSig] = {}
        self._event_manager = event_manager
        self._executors: dict[int, AbstractComponentExecutor] = {}
        self._gc_task: typing.Optional[asyncio.Task[None]] = None
        self._prefix_ids: dict[str, CallbackSig] = {}
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

        self._executors = {}
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

    def _match_constant_id(self, custom_id: str) -> typing.Optional[CallbackSig]:
        return self._constant_ids.get(custom_id) or self._prefix_ids.get(
            next(filter(custom_id.startswith, self._prefix_ids.keys()), "")
        )

    async def _execute_executor(
        self,
        executor: AbstractComponentExecutor,
        interaction: hikari.ComponentInteraction,
        /,
        *,
        future: typing.Optional[asyncio.Future[_ComponentResponseT]] = None,
    ) -> None:
        ctx = ComponentContext(self, interaction, self._add_task, response_future=future)

        try:
            await executor.execute(ctx)
        except ExecutorClosed:
            self._executors.pop(interaction.message.id, None)

    async def on_gateway_event(self, event: hikari.InteractionCreateEvent, /) -> None:
        """Process an interaction create gateway event.

        Parameters
        ----------
        event
            The interaction create gateway event to process.
        """
        if not isinstance(event.interaction, hikari.ComponentInteraction):
            return

        if constant_callback := self._match_constant_id(event.interaction.custom_id):
            ctx = ComponentContext(self, event.interaction, self._add_task, ephemeral_default=False)
            await self._alluka.call_with_async_di(constant_callback, ctx)

        elif executor := self._executors.get(event.interaction.message.id):
            await self._execute_executor(executor, event.interaction)

        else:
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE, "This message has timed-out.", flags=hikari.MessageFlag.EPHEMERAL
            )

    async def on_rest_request(self, interaction: hikari.ComponentInteraction, /) -> _ComponentResponseT:
        """Process a component interaction REST request.

        Parameters
        ----------
        interaction
            The interaction to process.

        Returns
        -------
        ResponseT
            The REST re sponse.
        """
        if constant_callback := self._match_constant_id(interaction.custom_id):
            future: asyncio.Future[_ComponentResponseT] = asyncio.Future()
            ctx = ComponentContext(self, interaction, self._add_task, ephemeral_default=False, response_future=future)
            self._add_task(asyncio.create_task(self._alluka.call_with_async_di(constant_callback, ctx)))
            return await future

        if executor := self._executors.get(interaction.message.id):
            if not executor.has_expired:
                future = asyncio.Future()
                self._add_task(asyncio.create_task(self._execute_executor(executor, interaction, future=future)))
                return await future

            del self._executors[interaction.message.id]

        return (
            interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
            .set_content("This message has timed-out.")
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    def set_constant_id(self, custom_id: str, callback: CallbackSig, /, *, prefix_match: bool = False) -> Self:
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

    def remove_constant_id(self, custom_id: str, /) -> Self:
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
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
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
        collections.abc.Callable[[CallbackSig], CallbackSig]
            A decorator to register the callback.

        Raises
        ------
        KeyError
            If the custom_id is already registered.
        """

        def decorator(callback: _CallbackSigT, /) -> _CallbackSigT:
            self.set_constant_id(custom_id, callback, prefix_match=prefix_match)
            return callback

        return decorator

    def set_executor(
        self, message: hikari.SnowflakeishOr[hikari.Message], executor: AbstractComponentExecutor, /
    ) -> Self:
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

    def remove_executor(self, message: hikari.SnowflakeishOr[hikari.Message], /) -> Self:
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


Client = ComponentClient
"""Alias of [ComponentClient][yuyo.components.ComponentClient]."""


class AbstractComponentExecutor(abc.ABC):
    """Abstract interface of an object which handles the execution of a message component."""

    __slots__ = ()

    @property
    @abc.abstractmethod
    def custom_ids(self) -> collections.Collection[str]:
        """Collection of the custom IDs this executor is listening for."""

    @property
    @abc.abstractmethod
    def has_expired(self) -> bool:
        """Whether this executor has ended."""

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


class ComponentExecutor(AbstractComponentExecutor):  # TODO: Not found action?
    """Basic implementation of a class used for handling the execution of a message component."""

    __slots__ = ("_ephemeral_default", "_id_to_callback", "_last_triggered", "_timeout")

    def __init__(
        self,
        *,
        ephemeral_default: bool = False,
        timeout: typing.Optional[datetime.timedelta] = datetime.timedelta(seconds=30),
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
        self._timeout = _to_timeout(timeout)

    @property
    def callbacks(self) -> collections.Mapping[str, CallbackSig]:
        """Mapping of custom IDs to their set callbacks."""
        return self._id_to_callback.copy()

    @property
    def custom_ids(self) -> collections.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._id_to_callback.keys()

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._timeout.has_expired

    async def execute(self, ctx: ComponentContext, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        ctx.set_ephemeral_default(self._ephemeral_default)
        callback = self._id_to_callback[ctx.interaction.custom_id]
        await ctx.client.alluka.call_with_async_di(callback, ctx)

    def set_callback(self, custom_id: str, callback: CallbackSig, /) -> Self:
        """Set the callback for a custom ID.

        Parameters
        ----------
        custom_id
            The custom ID to set the callback for.
        callback
            The callback to set.
        """
        self._id_to_callback[custom_id] = callback
        return self

    def with_callback(self, custom_id: str, /) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        """Set the callback for a custom ID through a decorator callback.

        Parameters
        ----------
        custom_id
            The custom ID to set the callback for.

        Returns
        -------
        collections.abc.Callable[[CallbackSig], CallbackSig]
            Decorator callback used to set a custom ID's callback.
        """

        def decorator(callback: _CallbackSigT, /) -> _CallbackSigT:
            self.set_callback(custom_id, callback)
            return callback

        return decorator


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

    __slots__ = ("_authors", "_ephemeral_default", "_finished", "_future", "_made_at", "_raw_timeout", "_timeout")

    def __init__(
        self,
        *,
        authors: typing.Optional[collections.Iterable[hikari.SnowflakeishOr[hikari.User]]],
        ephemeral_default: bool = False,
        timeout: typing.Optional[datetime.timedelta],
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
        self._raw_timeout = None if timeout is None else timeout.total_seconds()
        self._timeout = _to_timeout(timeout)

    @property
    def custom_ids(self) -> collections.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return []

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._timeout.has_expired

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
            return await asyncio.wait_for(self._future, self._raw_timeout)

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


class _TextSelectMenuBuilder(hikari.impl.TextSelectMenuBuilder[typing.NoReturn]):
    __slots__ = ()

    def build(self) -> collections.MutableMapping[str, typing.Any]:
        payload = super().build()
        max_values = min(len(self.options), self.max_values)
        payload["max_values"] = max_values
        return payload


class ActionRowExecutor(ComponentExecutor, hikari.api.ComponentBuilder):
    """Class used for handling the execution of an action row.

    You likely want [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
    instead as this provides an interface for handling all the components on a
    message.
    """

    __slots__ = ("_components", "_stored_type")

    def __init__(
        self,
        *,
        ephemeral_default: bool = False,
        timeout: typing.Optional[datetime.timedelta] = datetime.timedelta(seconds=30),
    ) -> None:
        """Initialise an action row executor.

        Parameters
        ----------
        ephemeral_default
            Whether this executor's responses should default to being ephemeral.
        timeout
            How long this component should last until its marked as timed out.
        """
        super().__init__(ephemeral_default=ephemeral_default, timeout=timeout)
        self._components: list[hikari.api.ComponentBuilder] = []
        self._stored_type: typing.Optional[hikari.ComponentType] = None

    @property
    def components(self) -> collections.Sequence[hikari.api.ComponentBuilder]:
        """The sub-components in this row."""
        return self._components.copy()

    @property
    def is_full(self) -> bool:
        """Whether this row is considered "full".

        For buttons the limit is 5. For other sub-components the limit is 1.
        """
        if self._components and isinstance(self._components[0], hikari.api.ButtonBuilder):
            return len(self._components) >= 5

        return bool(self._components)

    @property
    def type(self) -> typing.Literal[hikari.ComponentType.ACTION_ROW]:
        return hikari.ComponentType.ACTION_ROW

    def _assert_can_add_type(self, type_: hikari.ComponentType, /) -> Self:
        if self._stored_type is not None and self._stored_type != type_:
            raise ValueError(f"{type_} component type cannot be added to a container which already holds {type_}")

        self._stored_type = type_
        return self

    def add_component(self, component: hikari.api.ComponentBuilder, /) -> Self:
        """Add a sub-component to this action row.

        [ActionRowExecutor.set_callback][yuyo.components.ComponentExecutor.set_callback]
        should be used to set the callback for this component if it is interactive
        (has a `custom_id` field).

        Parameters
        ----------
        component
            The sub-component to add.

        Returns
        -------
        Self
            The action row to enable chained calls.
        """
        self._components.append(component)
        return self

    def add_button(
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
        """Add an interactive button to this action row.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The interactive button's style.
        callback
            The interactive button's callback.
        custom_id
            The button's custom ID.
        emoji
            The button's emoji.
        label
            The button's label.
        is_disabled
            Whether the button should be marked as disabled.

        Returns
        -------
        Self
            The action row to enable chained calls.

        Raises
        ------
        ValueError
            * If any of the sub-components in this action row aren't buttons.
            * If a callback is passed for `callback_or_url` for a url style button.
            * If a string is passed for `callback_or_url` for an interactive button.
        """
        self._assert_can_add_type(hikari.ComponentType.BUTTON)
        if custom_id is None:
            custom_id = _internal.random_custom_id()

        return self.set_callback(custom_id, callback).add_component(
            hikari.impl.InteractiveButtonBuilder(
                container=NotImplemented,
                custom_id=custom_id,
                style=hikari.ButtonStyle(style),
                label=label,
                is_disabled=is_disabled,
            ).set_emoji(emoji)
        )

    def add_link_button(
        self,
        url: str,
        /,
        *,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> Self:
        """Add a Link button to this action row.

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
            The action row to enable chained calls.

        Raises
        ------
        ValueError
            If any of the sub-components in this action row aren't buttons.
        """
        return self._assert_can_add_type(hikari.ComponentType.BUTTON).add_component(
            hikari.impl.LinkButtonBuilder(
                container=NotImplemented, style=hikari.ButtonStyle.LINK, url=url, label=label, is_disabled=is_disabled
            ).set_emoji(emoji)
        )

    def add_select_menu(
        self,
        callback: CallbackSig,
        type_: typing.Union[hikari.ComponentType, int],
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> Self:
        """Add a select menu to this action row.

        For channel select menus and text select menus see
        [ActionRowExecutor.add_channel_select][yuyo.components.ActionRowExecutor.add_channel_select] and
        [ActionRowExecutor.add_text_select][yuyo.components.ActionRowExecutor.add_text_select] respectively.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        type_
            The type of select menu to add.
        custom_id
            The select menu's custom ID.
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
            The action row to enable chained calls.
        """
        if custom_id is None:
            custom_id = _internal.random_custom_id()

        type_ = hikari.ComponentType(type_)
        return (
            self._assert_can_add_type(type_)
            .set_callback(custom_id, callback)
            .add_component(
                hikari.impl.SelectMenuBuilder(
                    container=NotImplemented,
                    custom_id=custom_id,
                    type=type_,
                    placeholder=placeholder,
                    min_values=min_values,
                    max_values=max_values,
                    is_disabled=is_disabled,
                )
            )
        )

    def add_channel_select(
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
        """Add a channel select menu to this action row.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        channel_types
            Sequence of the types of channels this select menu should show as options.
        custom_id
            The select menu's custom ID.
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
            The action row to enable chained calls.
        """
        if custom_id is None:
            custom_id = _internal.random_custom_id()

        return (
            self._assert_can_add_type(hikari.ComponentType.CHANNEL_SELECT_MENU)
            .set_callback(custom_id, callback)
            .add_component(
                hikari.impl.ChannelSelectMenuBuilder(
                    container=NotImplemented,
                    custom_id=custom_id,
                    channel_types=_parse_channel_types(*channel_types) if channel_types else [],
                    placeholder=placeholder,
                    min_values=min_values,
                    max_values=max_values,
                    is_disabled=is_disabled,
                )
            )
        )

    def add_text_select(
        self,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> hikari.api.TextSelectMenuBuilder[typing.NoReturn]:
        """Add a channel select menu to this action row.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.
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

            And the parent action row can be accessed by calling
            [TextSelectMenuBuilder.parent][hikari.api.special_endpoints.TextSelectMenuBuilder.parent].
        """
        if custom_id is None:
            custom_id = _internal.random_custom_id()

        component = _TextSelectMenuBuilder(
            container=NotImplemented,  # type: ignore
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )
        (
            self._assert_can_add_type(hikari.ComponentType.TEXT_SELECT_MENU)
            .set_callback(custom_id, callback)
            .add_component(component)
        )
        return component

    def build(self) -> dict[str, typing.Any]:
        # <<inherited docstring from ComponentBuilder>>.
        return {
            "type": hikari.ComponentType.ACTION_ROW,
            "components": [component.build() for component in self._components],
        }


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
    async def callback_1(ctx: components.ComponentContext) -> None:
        await ctx.respond("meow")

    components = (
        components.ActionColumnExecutor()
        .add_button(hikari.ButtonStyle.PRIMARY, chainable, label="Button 1")
        .add_link_button("https://example.com", label="Button 2",)
    )
    ```

    Alternatively, subclasses of [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
    can act as a template where "static" fields are included on all instances
    and subclasses of that class:

    ```py
    async def callback_1(ctx: components.ComponentContext) -> None:
        await ctx.respond("meow")

    async def callback_2(ctx: components.ComponentContext) -> None:
        await ctx.respond("meow")

    @components.with_static_select_menu(callback_1, hikari.ComponentType.USER_SELECT_MENU, max_values=5)
    class CustomColumn(components.ActionColumnExecutor):
        # The init can be overridden to store extra data on the column object when subclassing.
        def __init__(self, special_string: str, timeout: typing.Optional[datetime.timedelta] = None):
            super().__init__(timeout=timeout)
            self.special_string = special_string

    (
        CustomColumn.add_static_text_select(callback_2, min_values=0, max_values=3)
        # The following calls are all adding options to the added
        # text select menu.
        .add_option("Option 1", "value 1")
        .add_option("Option 2", "value 2")
        .add_option("Option 3", "value 3")
    )
    ```

    !!! note
        Since decorators are executed from the bottom upwards fields added
        through decorator calls will follow the same order.
    """

    __slots__ = ("_last_triggered", "_rows", "_timeout")

    _all_static_rows: typing.ClassVar[list[ActionRowExecutor]] = []
    _static_fields: typing.ClassVar[
        list[tuple[hikari.ComponentType, collections.Callable[[ActionRowExecutor], object]]]
    ] = []

    def __init__(self, *, timeout: typing.Optional[datetime.timedelta] = datetime.timedelta(seconds=30)) -> None:
        """Initialise an action column executor.

        Parameters
        ----------
        timeout
            How long this should wait for a matching component interaction until it times-out.
        """
        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        self._rows: list[ActionRowExecutor] = self._all_static_rows.copy()
        self._timeout = _to_timeout(timeout)

    def __init_subclass__(cls) -> None:
        cls._all_static_rows = []
        cls._static_fields = []

        for super_cls in cls.mro()[-2::-1]:
            if not issubclass(super_cls, ActionColumnExecutor):
                continue

            for component_type, callback in super_cls._static_fields:
                row = _append_row(cls._all_static_rows, is_button=component_type is hikari.ComponentType.BUTTON)
                callback(row)

    @property
    def custom_ids(self) -> collections.Collection[str]:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return list(itertools.chain.from_iterable(row.custom_ids for row in self._rows))

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractComponentExecutor>>.
        return self._timeout.has_expired

    @property
    def rows(self) -> collections.Sequence[ActionRowExecutor]:
        """The rows in this column."""
        return self._rows.copy()

    def add_row(self, row: ActionRowExecutor, /) -> Self:
        """Add an action row executor to this column.

        Parameters
        ----------
        row
            The action row executor to add.

        Returns
        -------
        Self
            The column executor to enable chained calls.
        """
        self._rows.append(row)
        return self

    async def execute(self, ctx: ComponentContext, /) -> None:
        # <<inherited docstring from AbstractComponentExecutor>>.
        for executor in self._rows:
            if ctx.interaction.custom_id in executor.custom_ids:
                await executor.execute(ctx)
                return

        raise KeyError("Custom ID not found")  # TODO: do we want to respond here?

    def add_button(
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
        _append_row(self._rows, is_button=True).add_button(
            style, callback, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
        )
        return self

    @classmethod
    def add_static_button(
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

        def _add_element(row: ActionRowExecutor, /) -> None:
            row.add_button(style, callback, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled)

        _add_element(_append_row(cls._all_static_rows, is_button=True))
        cls._static_fields.append((hikari.ComponentType.BUTTON, _add_element))
        return cls

    @classmethod
    def with_static_button(
        cls,
        style: hikari.InteractiveButtonTypesT,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
        label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        """Add an interactive button to this class by decorating its callback.

        Either `emoji` xor `label` must be provided to be the button's
        displayed label.

        Parameters
        ----------
        style
            The button's style.
        custom_id
            The button's custom ID.
        emoji
            The button's emoji.
        label
            The button's label.
        is_disabled
            Whether the button should be marked as disabled.

        Returns
        -------
        CallbackSig
            The decorated callback.

        Raises
        ------
        RuntimeError
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """

        def decorator(callback: _CallbackSigT, /) -> _CallbackSigT:
            cls.add_static_button(
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

        def _add_element(row: ActionRowExecutor, /) -> None:
            row.add_link_button(url, emoji=emoji, label=label, is_disabled=is_disabled)

        _add_element(_append_row(cls._all_static_rows, is_button=True))
        cls._static_fields.append((hikari.ComponentType.BUTTON, _add_element))
        return cls

    def add_select_menu(
        self,
        callback: CallbackSig,
        type_: typing.Union[hikari.ComponentType, int],
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> Self:
        """Add a select menu to this action column.

        For channel select menus and text select menus see
        [ActionColumnExecutor.add_channel_select][yuyo.components.ActionColumnExecutor.add_channel_select] and
        [ActionColumnExecutor.add_text_select][yuyo.components.ActionColumnExecutor.add_text_select] respectively.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        type_
            The type of select menu to add.
        custom_id
            The select menu's custom ID.
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
        _append_row(self._rows).add_select_menu(
            callback,
            type_,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )
        return self

    @classmethod
    def add_static_select_menu(
        cls,
        callback: CallbackSig,
        type_: typing.Union[hikari.ComponentType, int],
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> type[Self]:
        """Add a select menu to all subclasses and instances of this action column class.

        For channel select menus and text select menus see
        [ActionColumnExecutor.add_channel_select][yuyo.components.ActionColumnExecutor.add_channel_select] and
        [ActionColumnExecutor.add_text_select][yuyo.components.ActionColumnExecutor.add_text_select] respectively.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        type_
            The type of select menu to add.
        custom_id
            The select menu's custom ID.
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

        def _add_element(row: ActionRowExecutor, /) -> None:
            row.add_select_menu(
                callback,
                type_,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            )

        _add_element(_append_row(cls._all_static_rows))
        cls._static_fields.append((hikari.ComponentType(type_), _add_element))
        return cls

    @classmethod
    def with_static_select_menu(
        cls,
        type_: typing.Union[hikari.ComponentType, int],
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> collections.Callable[[_CallbackSigT], _CallbackSigT]:
        """Add a select menu to this class by decorating its callback.

        For channel select menus see
        [ActionColumnExecutor.with_static_channel_select][yuyo.components.ActionColumnExecutor.with_static_channel_select] .

        Parameters
        ----------
        type_
            The type of select menu to add.
        custom_id
            The select menu's custom ID.
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
        CallbackSig
            The decorated callback.

        Raises
        ------
        RuntimeError
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """

        def decorator(callback: _CallbackSigT, /) -> _CallbackSigT:
            cls.add_static_select_menu(
                callback,
                type_,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            )
            return callback

        return decorator

    def add_channel_select(
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
        _append_row(self._rows).add_channel_select(
            callback,
            custom_id=custom_id,
            channel_types=channel_types,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )
        return self

    @classmethod
    def add_static_channel_select(
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

        def _add_element(row: ActionRowExecutor, /) -> None:
            row.add_channel_select(
                callback,
                custom_id=custom_id,
                channel_types=channel_types,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            )

        _add_element(_append_row(cls._all_static_rows))
        cls._static_fields.append((hikari.ComponentType.CHANNEL_SELECT_MENU, _add_element))
        return cls

    @classmethod
    def with_static_channel_select(
        cls,
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
        """Add a channel select menu to this class by decorating its callback.

        Parameters
        ----------
        channel_types
            Sequence of the types of channels this select menu should show as options.
        custom_id
            The select menu's custom ID.
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
        CallbackSig
            The decorated callback.

        Raises
        ------
        RuntimeError
            When called directly on [components.ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
            (rather than on a subclass).
        """

        def decorator(callback: _CallbackSigT, /) -> _CallbackSigT:
            cls.add_static_channel_select(
                callback,
                custom_id=custom_id,
                channel_types=channel_types,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            )
            return callback

        return decorator

    def add_text_select(
        self,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> hikari.api.TextSelectMenuBuilder[typing.NoReturn]:
        """Add a channel select menu to this action column.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.
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
        return _append_row(self._rows).add_text_select(
            callback,
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            is_disabled=is_disabled,
        )

    @classmethod
    def add_static_text_select(
        cls,
        callback: CallbackSig,
        /,
        *,
        custom_id: typing.Optional[str] = None,
        placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
        min_values: int = 0,
        max_values: int = 1,
        is_disabled: bool = False,
    ) -> hikari.api.TextSelectMenuBuilder[typing.NoReturn]:
        """Add a channel select menu to all subclasses and instances of this action column class.

        Parameters
        ----------
        callback
            Callback which is called when this select menu is used.
        custom_id
            The select menu's custom ID.
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

        def _add_element(row: ActionRowExecutor, /) -> hikari.api.TextSelectMenuBuilder[typing.NoReturn]:
            return row.add_text_select(
                callback,
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                is_disabled=is_disabled,
            )

        select = _add_element(_append_row(cls._all_static_rows))
        cls._static_fields.append((hikari.ComponentType.TEXT_SELECT_MENU, _add_element))
        return select


def _append_row(rows: list[ActionRowExecutor], /, *, is_button: bool = False) -> ActionRowExecutor:
    if not rows or rows[-1].is_full:
        row = ActionRowExecutor(timeout=datetime.timedelta(days=200000))  # TODO: timeout = None
        rows.append(row)
        return row

    # This works since the other types all take up the whole row right now.
    if is_button or not rows[-1].components:
        return rows[-1]

    row = ActionRowExecutor(timeout=datetime.timedelta(days=200000))  # TODO: timeout = None
    rows.append(row)
    return row


def with_static_button(
    style: hikari.InteractiveButtonTypesT,
    callback: CallbackSig,
    /,
    *,
    custom_id: typing.Optional[str] = None,
    emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
    label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    is_disabled: bool = False,
) -> collections.Callable[[type[_ActionColumnExecutorT]], type[_ActionColumnExecutorT]]:
    """Add a static interactive button to the decorated action column class.

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
    emoji
        The button's emoji.
    label
        The button's label.
    is_disabled
        Whether the button should be marked as disabled.

    Returns
    -------
    type[Self]
        The decorated action column class.
    """
    return lambda executor: executor.add_static_button(
        style, callback, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
    )


def with_static_link_button(
    url: str,
    /,
    *,
    emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType] = hikari.UNDEFINED,
    label: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    is_disabled: bool = False,
) -> collections.Callable[[type[_ActionColumnExecutorT]], type[_ActionColumnExecutorT]]:
    """Add a static link button to the decorated action column class.

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
        The decorated action column class.
    """
    return lambda executor: executor.add_static_link_button(url, emoji=emoji, label=label, is_disabled=is_disabled)


def with_static_select_menu(
    callback: CallbackSig,
    type_: typing.Union[hikari.ComponentType, int],
    /,
    *,
    custom_id: typing.Optional[str] = None,
    placeholder: hikari.UndefinedOr[str] = hikari.UNDEFINED,
    min_values: int = 0,
    max_values: int = 1,
    is_disabled: bool = False,
) -> collections.Callable[[type[_ActionColumnExecutorT]], type[_ActionColumnExecutorT]]:
    """Add a static select menu to the decorated action column class.

    For channel select menus and text select menus see
    [ActionColumnExecutor.add_channel_select][yuyo.components.ActionColumnExecutor.add_channel_select] and
    [ActionColumnExecutor.add_text_select][yuyo.components.ActionColumnExecutor.add_text_select] respectively.

    Parameters
    ----------
    callback
        Callback which is called when this select menu is used.
    type_
        The type of select menu to add.
    custom_id
        The select menu's custom ID.
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
        The decorated action column class.
    """
    return lambda executor: executor.add_static_select_menu(
        callback,
        type_,
        custom_id=custom_id,
        placeholder=placeholder,
        min_values=min_values,
        max_values=max_values,
        is_disabled=is_disabled,
    )


def with_static_channel_select(
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
) -> collections.Callable[[type[_ActionColumnExecutorT]], type[_ActionColumnExecutorT]]:
    """Add a static channel select menu to the decorated action column class.

    Parameters
    ----------
    callback
        Callback which is called when this select menu is used.
    channel_types
        Sequence of the types of channels this select menu should show as options.
    custom_id
        The select menu's custom ID.
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
        The decorated action column class.
    """
    return lambda executor: executor.add_static_channel_select(
        callback,
        custom_id=custom_id,
        channel_types=channel_types,
        placeholder=placeholder,
        min_values=min_values,
        max_values=max_values,
        is_disabled=is_disabled,
    )


# TODO: with_static_text_select


class ComponentPaginator(ActionRowExecutor):
    """Standard implementation of an action row executor used for pagination.

    This is a convenience class that allows you to easily implement a paginator.
    """

    __slots__ = ("_authors", "_buffer", "_index", "_iterator", "_lock")

    def __init__(
        self,
        iterator: _internal.IteratorT[pagination.EntryT],
        /,
        *,
        authors: typing.Optional[collections.Iterable[hikari.SnowflakeishOr[hikari.User]]],
        ephemeral_default: bool = False,
        triggers: collections.Collection[str] = (
            pagination.LEFT_TRIANGLE,
            pagination.STOP_SQUARE,
            pagination.RIGHT_TRIANGLE,
        ),
        timeout: typing.Optional[datetime.timedelta] = datetime.timedelta(seconds=30),
    ) -> None:
        """Initialise a component paginator.

        Parameters
        ----------
        iterator : collections.Iterator[yuyo.pagination.EntryT] | collections.AsyncIterator[yuyo.pagination.EntryT]
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
            iterator, (collections.Iterator, collections.AsyncIterator)
        ):  # pyright: ignore [ reportUnnecessaryIsInstance ]
            raise TypeError(f"Invalid value passed for `iterator`, expected an iterator but got {type(iterator)}")

        super().__init__(ephemeral_default=ephemeral_default, timeout=timeout)

        self._authors = set(map(hikari.Snowflake, authors)) if authors else None
        self._buffer: list[pagination.Page] = []
        self._ephemeral_default = ephemeral_default
        self._index: int = -1
        self._iterator: typing.Optional[_internal.IteratorT[pagination.EntryT]] = iterator
        self._lock = asyncio.Lock()

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

        return self.add_button(
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

        return self.add_button(
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

        return self.add_button(
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

        return self.add_button(
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

        return self.add_button(
            style, self._on_last, custom_id=custom_id, emoji=emoji, label=label, is_disabled=is_disabled
        )

    def builder(self) -> collections.Sequence[hikari.api.ComponentBuilder]:
        """Get a sequence of the component builders for this paginator.

        Returns
        -------
        collections.abc.Sequence[hikari.api.ComponentBuilder]
            The component builders for this paginator.
        """
        return [self]

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
        response_paginator = yuyo.ComponentPaginator(
            pages,
            authors=(ctx.author.id,)
        )
        first_response = await response_paginator.get_next_entry()
        assert first_response
        message = await ctx.respond(component=response_paginator, **first_response.to_kwargs(), ensure_result=True)
        component_client.set_executor(message, response_paginator)
        ```

        Returns
        -------
        yuyo.pagination.Page | None
            The next entry in this paginator, or [None][] if there are no more entries.
        """
        # Check to see if we're behind the buffer before trying to go forward in the generator.
        if len(self._buffer) >= self._index + 2:
            self._index += 1
            return self._buffer[self._index]

        # If entry is not None then the generator's position was pushed forwards.
        if self._iterator and (entry := await _internal.seek_iterator(self._iterator, default=None)):
            entry = pagination.Page.from_entry(entry)
            self._index += 1
            self._buffer.append(entry)
            return entry

        return None  # MyPy

    async def _on_first(self, ctx: ComponentContext, /) -> None:
        if self._index != 0 and (first_entry := self._buffer[0] if self._buffer else await self.get_next_entry()):
            self._index = 0
            await ctx.create_initial_response(
                response_type=hikari.ResponseType.MESSAGE_UPDATE, **first_entry.to_kwargs()
            )

        else:
            await _noop(ctx)

    async def _on_previous(self, ctx: ComponentContext, /) -> None:
        if self._index > 0:
            self._index -= 1
            response = self._buffer[self._index]
            await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, **response.to_kwargs())

        else:
            await _noop(ctx)

    async def _on_disable(self, ctx: ComponentContext, /) -> None:
        self._iterator = None
        await ctx.defer(defer_type=hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
        await ctx.delete_initial_response()
        raise ExecutorClosed

    async def _on_last(self, ctx: ComponentContext, /) -> None:
        if self._iterator:
            # TODO: option to not lock on last
            loading_component = (
                ctx.interaction.app.rest.build_message_action_row()
                .add_button(hikari.ButtonStyle.SECONDARY, "loading")
                .set_is_disabled(True)
                .set_emoji(878377505344614461)
                .add_to_container()
            )
            await ctx.create_initial_response(
                component=loading_component, response_type=hikari.ResponseType.MESSAGE_UPDATE
            )
            self._buffer.extend(map(pagination.Page.from_entry, await _internal.collect_iterable(self._iterator)))
            self._index = len(self._buffer) - 1
            self._iterator = None

            if self._buffer:
                response = self._buffer[self._index]
                await ctx.edit_initial_response(components=self.builder(), **response.to_kwargs())

            else:
                await ctx.edit_initial_response(components=self.builder())

        elif self._buffer:
            self._index = len(self._buffer) - 1
            response = self._buffer[-1]
            await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, **response.to_kwargs())

        else:
            await _noop(ctx)

    async def _on_next(self, ctx: ComponentContext, /) -> None:
        if entry := await self.get_next_entry():
            await ctx.defer(defer_type=hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
            await ctx.edit_initial_response(**entry.to_kwargs())

        else:
            await _noop(ctx)


def _noop(ctx: ComponentContext, /) -> collections.Coroutine[typing.Any, typing.Any, None]:
    """Create a noop initial response to a component context."""
    return ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE)
