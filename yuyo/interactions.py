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
"""Base classes used for interaction handling."""
from __future__ import annotations

__all__ = ["BaseContext", "InteractionError"]

import abc
import asyncio
import datetime
import logging
import os
import typing
from collections import abc as collections

import hikari
from hikari import snowflakes

from . import _internal

if typing.TYPE_CHECKING:
    import alluka as alluka_
    from typing_extensions import Self


_InteractionT = typing.TypeVar("_InteractionT", hikari.ModalInteraction, hikari.ComponentInteraction)
_INTERACTION_LIFETIME: typing.Final[datetime.timedelta] = datetime.timedelta(minutes=15)
_ComponentResponseT = typing.Union[
    hikari.api.InteractionMessageBuilder, hikari.api.InteractionDeferredBuilder, hikari.api.InteractionModalBuilder
]
"""Type hint of the builder response types allows for component interactions."""

_LOGGER = logging.getLogger("hikari.yuyo.components")


def _delete_after_to_float(delete_after: typing.Union[datetime.timedelta, float, int], /) -> float:
    return delete_after.total_seconds() if isinstance(delete_after, datetime.timedelta) else float(delete_after)


_ATTACHMENT_TYPES: tuple[type[typing.Any], ...] = (hikari.files.Resource, *hikari.files.RAWISH_TYPES, os.PathLike)


class BaseContext(abc.ABC, typing.Generic[_InteractionT]):
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
        interaction: _InteractionT,
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
        """Initialise a base context."""
        self._ephemeral_default = ephemeral_default
        self._has_responded = False
        self._has_been_deferred = False
        self._id_match = id_match
        self._id_metadata = id_metadata
        self._interaction: _InteractionT = interaction
        self._last_response_id: typing.Optional[hikari.Snowflake] = None
        self._register_task = register_task
        self._response_future = response_future
        self._response_lock = asyncio.Lock()

    @property
    @abc.abstractmethod
    def alluka(self) -> alluka_.abc.Client:
        """The Alluka client being used for callback dependency injection."""
        raise NotImplementedError

    @property
    def author(self) -> hikari.User:
        """Author of this interaction."""
        return self._interaction.user

    @property
    @abc.abstractmethod
    def cache(self) -> typing.Optional[hikari.api.Cache]:
        """Hikari cache instance this context's client was initialised with."""

    @property
    def channel_id(self) -> hikari.Snowflake:
        """ID of the channel this interaction was triggered in."""
        return self._interaction.channel_id

    @property
    def created_at(self) -> datetime.datetime:
        return self._interaction.created_at

    @property
    def expires_at(self) -> datetime.datetime:
        """When this context expires.

        After this time is reached, the message/response methods on this
        context will always raise
        [hikari.NotFoundError][hikari.errors.NotFoundError].
        """
        return self._interaction.created_at + _INTERACTION_LIFETIME

    @property
    @abc.abstractmethod
    def events(self) -> typing.Optional[hikari.api.EventManager]:
        """Object of the event manager this context's client was initialised with."""

    @property
    def guild_id(self) -> typing.Optional[hikari.Snowflake]:
        return self._interaction.guild_id

    @property
    def has_been_deferred(self) -> bool:
        """Whether this context's initial response has been deferred.

        This will be true if [BaseContext.defer][yuyo.interactions.BaseContext.defer]
        has been called.
        """
        return self._has_been_deferred

    @property
    def has_responded(self) -> bool:
        """Whether an initial response has been made to this context yet.

        It's worth noting that a context must be either responded to or
        deferred within 3 seconds from it being received otherwise it'll be
        marked as failed.

        This will be true if either
        [BaseContext.respond][yuyo.interactions.BaseContext.respond],
        [BaseContext.create_initial_response][yuyo.interactions.BaseContext.create_initial_response]
        or [BaseContext.edit_initial_response][yuyo.interactions.BaseContext.edit_initial_response]
        (after a deferral) has been called.
        """
        return self._has_responded

    @property
    def id_match(self) -> str:
        """Section of the ID used to identify the relevant executor."""
        return self._id_match

    @property
    def id_metadata(self) -> str:
        """Metadata from the interaction's custom ID."""
        return self._id_metadata

    @property
    def interaction(self) -> _InteractionT:
        """Object of the interaction this context is for."""
        return self._interaction

    @property
    def member(self) -> typing.Optional[hikari.InteractionMember]:
        return self._interaction.member

    @property
    @abc.abstractmethod
    def rest(self) -> typing.Optional[hikari.api.RESTClient]:
        """Object of the Hikari REST client this context's client was initialised with."""

    @property
    @abc.abstractmethod
    def server(self) -> typing.Optional[hikari.api.InteractionServer]:
        """Object of the Hikari interaction server provided for this context's client."""

    @property
    @abc.abstractmethod
    def shards(self) -> typing.Optional[hikari.ShardAware]:
        """Object of the Hikari shard manager this context's client was initialised with."""

    @property
    def shard(self) -> typing.Optional[hikari.api.GatewayShard]:
        """Shard that triggered the interaction.

        !!! note
            This will be [None][] if [BaseContext.shards][yuyo.interactions.BaseContext.shards]
            is also [None][].
        """
        if not self.shards:
            return None

        if self.guild_id is not None:
            shard_id = snowflakes.calculate_shard_id(self.shards, self.guild_id)

        else:
            shard_id = 0

        return self.shards.shards[shard_id]

    @property
    @abc.abstractmethod
    def voice(self) -> typing.Optional[hikari.api.VoiceComponent]:
        """Object of the Hikari voice component this context's client was initialised with."""

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

    def _get_flags(
        self,
        flags: typing.Union[hikari.UndefinedType, int, hikari.MessageFlag] = hikari.UNDEFINED,
        /,
        *,
        ephemeral: typing.Optional[bool] = None,
        is_create: bool = True,
    ) -> typing.Union[int, hikari.MessageFlag]:
        if flags is hikari.UNDEFINED:
            if ephemeral is True or (ephemeral is None and is_create and self._ephemeral_default):
                return hikari.MessageFlag.EPHEMERAL

            return hikari.MessageFlag.NONE

        if ephemeral is True:
            return flags | hikari.MessageFlag.EPHEMERAL

        if ephemeral is False:
            return flags & ~hikari.MessageFlag.EPHEMERAL

        return flags

    async def defer(
        self,
        *,
        defer_type: hikari.DeferredResponseTypesT = hikari.ResponseType.DEFERRED_MESSAGE_CREATE,
        ephemeral: typing.Optional[bool] = None,
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

            This may any of the following:

            * [ResponseType.DEFERRED_MESSAGE_CREATE][hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_CREATE]
                to indicate that the following up call to
                [BaseContext.edit_initial_response][yuyo.interactions.BaseContext.edit_initial_response]
                or [BaseContext.respond][yuyo.interactions.BaseContext.respond]
                should create a new message.
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
        flags = self._get_flags(
            flags, ephemeral=ephemeral, is_create=defer_type == hikari.ResponseType.DEFERRED_MESSAGE_CREATE
        )

        async with self._response_lock:
            if self._has_been_deferred:
                raise RuntimeError("Context has already been responded to")

            self._has_been_deferred = True
            if self._response_future:
                # TODO: ModalInteraction.build_deferred_response needs to support defer_type
                self._response_future.set_result(hikari.impl.InteractionDeferredBuilder(defer_type, flags=flags))

            else:
                await self._interaction.create_initial_response(defer_type, flags=flags)

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
        ephemeral: typing.Optional[bool] = None,
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
            flags=self._get_flags(flags, ephemeral=ephemeral),
            tts=tts,
            mentions_everyone=mentions_everyone,
            user_mentions=user_mentions,
            role_mentions=role_mentions,
        )
        self._last_response_id = message.id
        # This behaviour is undocumented and only kept by Discord for "backwards compatibility"
        # but the followup endpoint can be used to create the initial response for interactions
        # or edit in a deferred response and (while this does lead to some unexpected behaviour
        # around deferrals) should be accounted for.
        self._has_responded = True

        if delete_after is not None:
            self._register_task(asyncio.create_task(self._delete_followup_after(delete_after, message)))

        return message

    async def create_followup(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
        ephemeral: typing.Optional[bool] = None,
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
            will lead to a [hikari.NotFoundError][hikari.errors.NotFoundError]
            being raised.

        Parameters
        ----------
        content
            If provided, the message content to send.

            If this is a [hikari.Embed][hikari.embeds.Embed] and no `embed` nor
            `embeds` kwarg is provided, then this will instead be treated as an
            embed. This allows for simpler syntax when sending an embed alone.

            Likewise, if this is a [hikari.Resource][hikari.files.Resource],
            then the content is instead treated as an attachment if no
            `attachment` and no `attachments` kwargs are provided.
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Interaction responses can only be deleted within 15 minutes of the
            interaction being received.
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
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialUser][hikari.users.PartialUser]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialRole][hikari.guilds.PartialRole]
            derivatives to enforce mentioning specific roles.
        tts
            If provided, whether the message will be sent as a TTS message.
        flags
            The flags to set for this response.

            As of writing this can only flag which can be provided is EPHEMERAL,
            other flags are just ignored.

        Returns
        -------
        hikari.messages.Message
            The created message object.

        Raises
        ------
        hikari.errors.NotFoundError
            If the current interaction is not found or it hasn't had an initial
            response yet.
        hikari.errors.BadRequestError
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
        async with self._response_lock:
            return await self._create_followup(
                content=content,
                delete_after=delete_after,
                ephemeral=ephemeral,
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
        ephemeral: typing.Optional[bool] = None,
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
        flags = self._get_flags(
            flags, ephemeral=ephemeral, is_create=response_type == hikari.ResponseType.MESSAGE_CREATE
        )
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
            attachments, content = _internal.to_list(attachment, attachments, content, _ATTACHMENT_TYPES, "attachment")
            components, content = _internal.to_list(
                component, components, content, hikari.api.ComponentBuilder, "component"
            )
            embeds, content = _internal.to_list(embed, embeds, content, hikari.Embed, "embed")

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

    async def create_initial_response(
        self,
        content: hikari.UndefinedOr[typing.Any] = hikari.UNDEFINED,
        *,
        response_type: hikari.MessageResponseTypesT = hikari.ResponseType.MESSAGE_CREATE,
        delete_after: typing.Union[datetime.timedelta, float, int, None] = None,
        ephemeral: typing.Optional[bool] = None,
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
            will result in this raising a
            [hikari.NotFoundError][hikari.errors.NotFoundError]. This includes
            if the REST interaction server has already responded to the request
            and deferrals.

        Parameters
        ----------
        content
            If provided, the message content to respond with.

            If this is a [hikari.Embed][hikari.embeds.Embed] and no `embed` nor
            `embeds` kwarg is provided, then this will instead be treated as an
            embed. This allows for simpler syntax when sending an embed alone.

            Likewise, if this is a [hikari.Resource][hikari.files.Resource],
            then the content is instead treated as an attachment if no
            `attachment` and no `attachments` kwargs are provided.
        response_type
            The type of message response to give.
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Interaction responses can only be deleted within 15 minutes of the
            interaction being received.
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
        flags
            If provided, the message flags this response should have.

            As of writing the only message flag which can be set here is
            [MessageFlag.EPHEMERAL][hikari.messages.MessageFlag.EPHEMERAL].
        tts
            If provided, whether the message will be read out by a screen
            reader using Discord's TTS (text-to-speech) system.
        mentions_everyone
            If provided, whether the message should parse @everyone/@here
            mentions.
        user_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialUser][hikari.users.PartialUser]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialRole][hikari.guilds.PartialRole]
            derivatives to enforce mentioning specific roles.

        Raises
        ------
        ValueError
            If more than 100 unique objects/entities are passed for
            `role_mentions` or `user_mentions`.

            If the interaction will have expired before `delete_after` is reached.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        hikari.errors.BadRequestError
            This may be raised in several discrete situations, such as messages
            being empty with no embeds; messages with more than
            2000 characters in them, embeds that exceed one of the many embed
            limits; invalid image URLs in embeds.
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.NotFoundError
            If the interaction is not found or if the interaction's initial
            response has already been created.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        async with self._response_lock:
            await self._create_initial_response(
                response_type,
                delete_after=delete_after,
                ephemeral=ephemeral,
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
        LookupError, hikari.errors.NotFoundError
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
        LookupError, hikari.errors.NotFoundError
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
            If provided, the message content to edit the initial response with.

            If this is a [hikari.Embed][hikari.embeds.Embed] and no `embed` nor
            `embeds` kwarg is provided, then this will instead update the embed.
            This allows for simpler syntax when sending an embed alone.

            Likewise, if this is a [hikari.Resource][hikari.files.Resource],
            then the content is instead treated as an attachment if no
            `attachment` and no `attachments` kwargs are provided.
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Interaction responses can only be deleted within 15 minutes of
            the interaction being received.
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
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialUser][hikari.users.PartialUser]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialRole][hikari.guilds.PartialRole]
            derivatives to enforce mentioning specific roles.

        Returns
        -------
        hikari.messages.Message
            The message that has been edited.

        Raises
        ------
        ValueError
            If more than 100 unique objects/entities are passed for
            `role_mentions` or `user_mentions`.

            If `delete_after` would be more than 15 minutes after the
            interaction was received.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        hikari.errors.BadRequestError
            This may be raised in several discrete situations, such as messages
            being empty with no attachments or embeds; messages with more than
            2000 characters in them, embeds that exceed one of the many embed
            limits; too many attachments; attachments that are too large;
            invalid image URLs in embeds; too many components.
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.ForbiddenError
            If you are missing the `SEND_MESSAGES` in the channel or the
            person you are trying to message has the DM's disabled.
        hikari.errors.NotFoundError
            If the channel is not found.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
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
            If provided, the content to edit the last response with.

            If this is a [hikari.Embed][hikari.embeds.Embed] and no `embed` nor
            `embeds` kwarg is provided, then this will instead update the embed.
            This allows for simpler syntax when sending an embed alone.

            Likewise, if this is a [hikari.Resource][hikari.files.Resource],
            then the content is instead treated as an attachment if no
            `attachment` and no `attachments` kwargs are provided.
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Interaction responses can only be deleted within 15 minutes of
            the interaction being received.
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
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialUser][hikari.users.PartialUser]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialRole][hikari.guilds.PartialRole]
            derivatives to enforce mentioning specific roles.

        Returns
        -------
        hikari.messages.Message
            The message that has been edited.

        Raises
        ------
        ValueError
            If more than 100 unique objects/entities are passed for
            `role_mentions` or `user_mentions`.

            If `delete_after` would be more than 15 minutes after the slash
            interaction was received.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        hikari.errors.BadRequestError
            This may be raised in several discrete situations, such as messages
            being empty with no attachments or embeds; messages with more than
            2000 characters in them, embeds that exceed one of the many embed
            limits; too many attachments; attachments that are too large;
            invalid image URLs in embeds; too many components.
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.ForbiddenError
            If you are missing the `SEND_MESSAGES` in the channel or the
            person you are trying to message has the DM's disabled.
        hikari.errors.NotFoundError
            If the channel is not found.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
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
        LookupError, hikari.errors.NotFoundError
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
        LookupError, hikari.errors.NotFoundError
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
    ) -> hikari.Message: ...

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
    ) -> typing.Optional[hikari.Message]: ...

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
            If provided, the message content to respond with.

            If this is a [hikari.Embed][hikari.embeds.Embed] and no `embed` nor
            `embeds` kwarg is provided, then this will instead be treated as an
            embed. This allows for simpler syntax when sending an embed alone.

            Likewise, if this is a [hikari.Resource][hikari.files.Resource],
            then the content is instead treated as an attachment if no
            `attachment` and no `attachments` kwargs are provided.
        ensure_result
            Ensure that this call will always return a message object.

            If [True][] then this will always return
            [hikari.Message][hikari.messages.Message], otherwise this will
            return `hikari.Message | None`.

            It's worth noting that this may lead to an extre request being made
            under certain scenarios.
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Interaction responses can only be deleted within 15 minutes of
            the interaction being received.
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
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialUser][hikari.users.PartialUser]
            derivatives to enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialRole][hikari.guilds.PartialRole]
            derivatives to enforce mentioning specific roles.

        Returns
        -------
        hikari.messages.Message | None
            The message that has been created if it was immedieatly available or
            `ensure_result` was set to [True][], else [None][].

        Raises
        ------
        ValueError
            If more than 100 unique objects/entities are passed for
            `role_mentions` or `user_mentions`.

            If `delete_after` would be more than 15 minutes after the
            interaction was received.

            If both `attachment` and `attachments` are passed or both `component`
            and `components` are passed or both `embed` and `embeds` are passed.
        hikari.errors.BadRequestError
            This may be raised in several discrete situations, such as messages
            being empty with no attachments or embeds; messages with more than
            2000 characters in them, embeds that exceed one of the many embed
            limits; too many attachments; attachments that are too large;
            invalid image URLs in embeds; too many components.
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.ForbiddenError
            If you are missing the `SEND_MESSAGES` in the channel or the
            person you are trying to message has the DM's disabled.
        hikari.errors.NotFoundError
            If the channel is not found.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
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


class InteractionError(Exception):
    """Error which is sent as a response to a modal or component call."""

    def __init__(
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
    ) -> None:
        """Initialise an interaction error.

        Parameters
        ----------
        content
            If provided, the message content to respond with.

            If this is a [hikari.Embed][hikari.embeds.Embed] and no `embed` nor
            `embeds` kwarg is provided, then this will instead be treated as an
            embed. This allows for simpler syntax when sending an embed alone.

            Likewise, if this is a [hikari.Resource][hikari.files.Resource],
            then the content is instead treated as an attachment if no
            `attachment` and no `attachments` kwargs are provided.
        delete_after
            If provided, the seconds after which the response message should be deleted.

            Interaction responses can only be deleted within 15 minutes of
            the interaction being received.
        attachment
            A singular attachment to respond with.
        attachments
            A sequence of attachments to respond with.
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
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialUser][hikari.users.PartialUser] derivatives to
            enforce mentioning specific users.
        role_mentions
            If provided, and [True][], all mentions will be parsed.
            If provided, and [False][], no mentions will be parsed.

            Alternatively this may be a collection of
            [hikari.Snowflake][hikari.snowflakes.Snowflake], or
            [hikari.PartialRole][hikari.guilds.PartialRole] derivatives to
            enforce mentioning specific roles.

        Raises
        ------
        ValueError
            Raised for any of the following reasons:

            * When both `attachment` and `attachments` are provided.
            * When both `component` and `components` are passed.
            * When both `embed` and `embeds` are passed.
            * If more than 100 entries are passed for `role_mentions`.
            * If more than 100 entries are passed for `user_mentions`.
        """
        if attachment and attachments:
            raise ValueError("Cannot specify both attachment and attachments")

        if component and components:
            raise ValueError("Cannot specify both component and components")

        if embed and embeds:
            raise ValueError("Cannot specify both embed and embeds")

        if isinstance(role_mentions, collections.Sequence) and len(role_mentions) > 100:
            raise ValueError("Cannot specify more than 100 role mentions")

        if isinstance(user_mentions, collections.Sequence) and len(user_mentions) > 100:
            raise ValueError("Cannot specify more than 100 user mentions")

        self._attachments = [attachment] if attachment else attachments
        self._content = content
        self._components = [component] if component else components
        self._delete_after = delete_after
        self._embeds = [embed] if embed else embeds
        self._mentions_everyone = mentions_everyone
        self._role_mentions = role_mentions
        self._user_mentions = user_mentions

    def __str__(self) -> str:
        return self._content or ""

    @typing.overload
    async def send(
        self,
        ctx: typing.Union[BaseContext[hikari.ComponentInteraction], BaseContext[hikari.ModalInteraction]],
        /,
        *,
        ensure_result: typing.Literal[True],
    ) -> hikari.Message: ...

    @typing.overload
    async def send(
        self,
        ctx: typing.Union[BaseContext[hikari.ComponentInteraction], BaseContext[hikari.ModalInteraction]],
        /,
        *,
        ensure_result: bool = False,
    ) -> typing.Optional[hikari.Message]: ...

    async def send(
        self,
        ctx: typing.Union[BaseContext[hikari.ComponentInteraction], BaseContext[hikari.ModalInteraction]],
        /,
        *,
        ensure_result: bool = False,
    ) -> typing.Optional[hikari.Message]:
        """Send this error as an interaction response.

        Parameters
        ----------
        ctx
            The interaction context to respond to.
        ensure_result
            Ensure that this call will always return a message object.

            If [True][] then this will always return
            [hikari.Message][hikari.messages.Message], otherwise this will
            return `hikari.Message | None`.

            It's worth noting that this may lead to an extra request being made
            under certain scenarios.

        Raises
        ------
        ValueError
            If `delete_after` would be more than 15 minutes after the
            interaction was received.
        hikari.errors.BadRequestError
            This may be raised in several discrete situations, such as messages
            being empty with no attachments or embeds; messages with more than
            2000 characters in them, embeds that exceed one of the many embed
            limits; too many attachments; attachments that are too large;
            invalid image URLs in embeds; too many components.
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.ForbiddenError
            If you are missing the `SEND_MESSAGES` in the channel or the
            person you are trying to message has the DM's disabled.
        hikari.errors.NotFoundError
            If the channel is not found.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        return await ctx.respond(
            content=self._content,
            attachments=self._attachments,
            components=self._components,
            delete_after=self._delete_after,
            embeds=self._embeds,
            ensure_result=ensure_result,
            mentions_everyone=self._mentions_everyone,
            role_mentions=self._role_mentions,
            user_mentions=self._user_mentions,
        )
