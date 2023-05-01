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
"""Classes and functions for handling Discord Links."""
from __future__ import annotations

__all__: list[str] = [
    "ChannelLink",
    "InviteLink",
    "MessageLink",
    "TemplateLink",
    "WebhookLink",
    "make_bot_invite",
    "make_channel_link",
    "make_invite_link",
    "make_message_link",
    "make_oauth_link",
    "make_template_link",
    "make_webhook_link",
]

import abc
import dataclasses
import re
import typing
import urllib.parse

import hikari
import hikari.urls

if typing.TYPE_CHECKING:
    from collections import abc as collections

    from typing_extensions import Self

_SUB_DOMAIN = r"(?:www\.|ptb\.|canary\.)?"


class BaseLink(abc.ABC):
    """Base class for all link objects."""

    __slots__ = ()

    _FIND_PATTERN: typing.ClassVar[re.Pattern[str]]
    _MATCH_PATTERN: typing.ClassVar[re.Pattern[str]]

    @classmethod
    def find(cls, app: hikari.RESTAware, content: str, /) -> typing.Optional[Self]:
        """Find the first link in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        Self | None
            Object of the found link or [None][].
        """
        return next(cls.find_iter(app, content), None)

    @classmethod
    def find_iter(cls, app: hikari.RESTAware, content: str, /) -> collections.Iterator[Self]:
        """Iterate over the links in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        collections.abc.Iterator[Self]
            Iterator of the link objects in the passed string.
        """
        for match in cls._FIND_PATTERN.finditer(content):
            yield cls._from_match(app, match)

    @classmethod
    def from_link(cls, app: hikari.RESTAware, link: str, /) -> Self:
        """Create a link object from a raw link.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        link
            The string link to use.

        Returns
        -------
        Self
            The created link object.

        Raises
        ------
        ValueError
            If the string doesn't match the expected link format.
        """
        if match := cls._MATCH_PATTERN.fullmatch(link.strip()):
            return cls._from_match(app, match)

        raise ValueError("Link doesn't match pattern")

    @classmethod
    @abc.abstractmethod
    def _from_match(cls, app: hikari.RESTAware, match: re.Match[str], /) -> Self:
        raise NotImplementedError


def make_channel_link(
    channel: hikari.SnowflakeishOr[hikari.PartialChannel],
    /,
    *,
    guild: typing.Optional[hikari.SnowflakeishOr[hikari.PartialGuild]] = None,
) -> str:
    """Make a raw link for a channel.

    Parameters
    ----------
    channel
        Object or ID of the channel to link to.
    guild
        Object or ID of the guild the channel is in.

        This should be provided for guild links.

    Returns
    -------
    str
        The raw channel link.
    """
    guild_ = "@me" if guild is None else int(guild)
    return f"{hikari.urls.BASE_URL}/channels/{guild_}/{int(channel)}"


@dataclasses.dataclass
class ChannelLink(BaseLink):
    """Represents a link to a channel.

    The following class methods are used to initialise this:

    * [InviteLink.from_link][yuyo.links.BaseLink.from_link] to create this from
      a raw channel link.
    * [InviteLink.find][yuyo.links.BaseLink.find] to find the first channel link
      in a string.
    * [InviteLink.find_iter][yuyo.links.BaseLink.find_iter] to iterate over the
      channel links in a string.
    """

    __slots__ = ("_app", "_guild_id", "_channel_id")

    _app: hikari.RESTAware
    _guild_id: typing.Optional[hikari.Snowflake]
    _channel_id: hikari.Snowflake

    _FIND_PATTERN = _MATCH_PATTERN = re.compile(
        r"https?://" + _SUB_DOMAIN + r"discord(?:app)?\.com/channels/(\d+|@me)/(\d+)(?:/\d+)?"
    )

    def __str__(self) -> str:
        """Create a raw string representation of this link."""
        return make_channel_link(self._channel_id, guild=self._guild_id)

    @classmethod
    def _from_match(cls, app: hikari.RESTAware, match: re.Match[str], /) -> Self:
        guild_id, channel_id = match.groups()
        guild_id = None if guild_id == "@me" else hikari.Snowflake(guild_id)
        return cls(_app=app, _channel_id=hikari.Snowflake(channel_id), _guild_id=guild_id)

    @property
    def channel_id(self) -> hikari.Snowflake:
        """ID of the channel this links to."""
        return self._channel_id

    @property
    def guild_id(self) -> typing.Optional[hikari.Snowflake]:
        """ID of the guild this links to.

        Will be [None][] for DM links.
        """
        return self._guild_id

    @property
    def is_dm_link(self) -> bool:
        """Whether this links to a DM channel."""
        return self._guild_id is None

    async def fetch_channel(self) -> hikari.PartialChannel:
        """Fetch the channel this links to.

        Returns
        -------
        hikari.channels.PartialChannel
            The this links to channel. This will be a _derivative_ of
            `hikari.channels.PartialChannel`, depending on the type of
            channel you request for.

        Raises
        ------
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.ForbiddenError
            If you are missing the `READ_MESSAGES` permission in the channel.
        hikari.errors.NotFoundError
            If the channel is not found.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        return await self._app.rest.fetch_channel(self._channel_id)

    def get_channel(self) -> typing.Optional[hikari.GuildChannel]:
        """Get the channel this links to from the cache.

        Returns
        -------
        hikari.channels.GuildChannel | None
            Object of the guild channel that was found in the cache or [None][].
        """
        if isinstance(self._app, hikari.CacheAware):
            return self._app.cache.get_guild_channel(self._channel_id) or self._app.cache.get_thread(self._channel_id)

        return None  # MyPy compat

    async def fetch_guild(self) -> typing.Optional[hikari.RESTGuild]:
        """Fetch the guild this links to.

        Returns
        -------
        hikari.guilds.RESTGuild | None
            Object of the guild this links to.

            Will be [None][] if this links to a DM channel.

        Raises
        ------
        hikari.errors.ForbiddenError
            If you are not part of the guild.
        hikari.errors.NotFoundError
            If the guild is not found.
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        if self._guild_id:
            return await self._app.rest.fetch_guild(self._guild_id)

        return None  # Mypy compat

    def get_guild(self) -> typing.Optional[hikari.GatewayGuild]:
        """Get the guild this links to from the cache.

        Returns
        -------
        hikari.channels.GuildChannel | None
            Object of the guild that was found in the cache or [None][].

            This will also be [None][] if this links to a DM channel.
        """
        if self._guild_id and isinstance(self._app, hikari.CacheAware):
            return self._app.cache.get_guild(self._guild_id)

        return None  # MyPy compat


def make_invite_link(invite: typing.Union[str, hikari.InviteCode], /) -> str:
    """Make a raw link for an invite.

    Parameters
    ----------
    invite
        Object or string code of the invite to make a raw link for.

    Returns
    -------
    str
        The raw invite link.
    """
    invite_code = invite.code if isinstance(invite, hikari.InviteCode) else invite
    return f"https://discord.gg/{invite_code}"


@dataclasses.dataclass
class InviteLink(hikari.InviteCode, BaseLink):
    """Represents a Discord invite link.

    The following class methods are used to initialise this:

    * [InviteLink.from_link][yuyo.links.BaseLink.from_link] to create this from
      a raw invite link.
    * [InviteLink.find][yuyo.links.BaseLink.find] to find the first invite link
      in a string.
    * [InviteLink.find_iter][yuyo.links.BaseLink.find_iter] to iterate over the
      invite links in a string.
    """

    __slots__ = ("_app", "_code")

    _app: hikari.RESTAware
    _code: str

    # The logic which embeds invites is special and doesn't require
    # `https://(?:www\.)?` so we match this behaviour even though the client
    # still isn't actually treating it as a link.
    _FIND_PATTERN = re.compile(r"discord(?:\.gg|(?:app)?\.com/invite)/([^\s/]+)")
    _MATCH_PATTERN = re.compile(r"(?:https?://)?" + _SUB_DOMAIN + _FIND_PATTERN.pattern)

    @property
    def code(self) -> str:
        """The invite's code."""
        return self._code

    @classmethod
    def _from_match(cls, app: hikari.RESTAware, match: re.Match[str], /) -> Self:
        return cls(_app=app, _code=match.groups()[0])

    async def fetch_invite(self) -> hikari.Invite:
        """Fetch the invite this links to.

        Returns
        -------
        hikari.invites.Invite
            Object of the invite this links to.

        Raises
        ------
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.NotFoundError
            If the invite is not found.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        return await self._app.rest.fetch_invite(self._code)

    def get_invite(self) -> typing.Optional[hikari.InviteWithMetadata]:
        """Get the invite this links to from the cache.

        Returns
        -------
        hikari.invites.InviteWithMetadata | None
            Object of the invite that was found in the cache or [None][].
        """
        if isinstance(self._app, hikari.CacheAware):
            return self._app.cache.get_invite(self._code)

        return None  # MyPy compat


def make_message_link(
    channel: hikari.SnowflakeishOr[hikari.PartialChannel],
    message: hikari.SnowflakeishOr[hikari.PartialMessage],
    /,
    *,
    guild: typing.Optional[hikari.SnowflakeishOr[hikari.PartialGuild]] = None,
) -> str:
    """Make a raw link for a message.

    Parameters
    ----------
    channel
        Object or ID of the channel the message is in.
    message
        Object or ID of the message to link to.
    guild
        Object or ID of the guild the message is in.

        This should be provided for messages in guilds.

    Returns
    -------
    str
        The raw message link.
    """
    return make_channel_link(channel, guild=guild) + f"/{int(message)}"


@dataclasses.dataclass
class MessageLink(ChannelLink):
    """Represents a link to a message on Discord.

    The following class methods are used to initialise this:

    * [MessageLink.from_link][yuyo.links.BaseLink.from_link] to create this
      from a raw message link.
    * [MessageLink.find][yuyo.links.BaseLink.find] to find the first invite
      link in a string.
    * [MessageLink.find_iter][yuyo.links.BaseLink.find_iter] to iterate over
      the message links in a string.
    """

    __slots__ = ("_message_id",)

    _message_id: hikari.Snowflake

    _FIND_PATTERN = _MATCH_PATTERN = re.compile(
        r"https?://" + _SUB_DOMAIN + r"discord(?:app)?\.com/channels/(\d+|@me)/(\d+)/(\d+)"
    )

    def __str__(self) -> str:
        """Create a raw string representation of this link."""
        return make_message_link(self._channel_id, self._message_id, guild=self._guild_id)

    @property
    def message_id(self) -> hikari.Snowflake:
        """ID of the message this links to."""
        return self._message_id

    @classmethod
    def _from_match(cls, app: hikari.RESTAware, match: re.Match[str], /) -> Self:
        guild_id, channel_id, message_id = match.groups()
        guild_id = None if guild_id == "@me" else hikari.Snowflake(guild_id)
        return cls(
            _app=app,
            _channel_id=hikari.Snowflake(channel_id),
            _guild_id=guild_id,
            _message_id=hikari.Snowflake(message_id),
        )

    async def fetch_message(self) -> hikari.Message:
        """Fetch a the message this links to.

        Returns
        -------
        hikari.messages.Message
            Object of the message this links to.

        Raises
        ------
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.ForbiddenError
            If you are missing the `READ_MESSAGE_HISTORY` in the channel.
        hikari.errors.NotFoundError
            If the channel is not found or the message is not found in the
            given text channel.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        return await self._app.rest.fetch_message(self._channel_id, self._message_id)

    def get_message(self) -> typing.Optional[hikari.Message]:
        """Get the message this links to from the cache.

        Returns
        -------
        hikari.messages.Message | None
            Object of the message that was found in the cache or [None][].
        """
        if isinstance(self._app, hikari.CacheAware):
            return self._app.cache.get_message(self._message_id)

        return None


def make_template_link(template: typing.Union[hikari.Template, str], /) -> str:
    """Make a raw link for a guild template.

    Parameters
    ----------
    template
        Object or string code of the template to make a raw link to.

    Returns
    -------
    str
        The raw template link.
    """
    template_code = template.code if isinstance(template, hikari.Template) else template
    return f"https://discord.new/{template_code}"


@dataclasses.dataclass
class TemplateLink(BaseLink):
    """Represents a link to a guild template.

    The following class methods are used to initialise this:

    * [TemplateLink.from_link][yuyo.links.BaseLink.from_link] to create this
      from a raw template link.
    * [TemplateLink.find][yuyo.links.BaseLink.find] to find the first template
      link in a string.
    * [TemplateLink.find_iter][yuyo.links.BaseLink.find_iter] to iterate over
      the template links in a string.
    """

    __slots__ = ("_app", "_code")

    _app: hikari.RESTAware
    _code: str

    _FIND_PATTERN = _MATCH_PATTERN = re.compile(
        r"https?://" + _SUB_DOMAIN + r"discord(?:\.new|(?:app)?\.com/template)/([^\s/]+)"
    )

    def __str__(self) -> str:
        """Create a raw string representation of this link."""
        return make_template_link(self._code)

    @property
    def code(self) -> str:
        """The template's code."""
        return self._code

    @classmethod
    def _from_match(cls, app: hikari.RESTAware, match: re.Match[str], /) -> Self:
        return cls(_app=app, _code=match.groups()[0])

    async def fetch_template(self) -> hikari.Template:
        """Fetch the guild template this links to.

        Returns
        -------
        hikari.templates.Template
            Object of the guild template this links to.

        Raises
        ------
        hikari.errors.NotFoundError
            If the template was not found.
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        return await self._app.rest.fetch_template(self._code)


def make_webhook_link(webhook: hikari.SnowflakeishOr[hikari.PartialWebhook], token: str, /) -> str:
    """Make a raw link for an incoming webhook.

    Parameters
    ----------
    webhook
        Object or ID of the webhook to make a link for.
    token
        The webhook's token.

    Returns
    -------
    str
        The raw webhook link.
    """
    return f"{hikari.urls.BASE_URL}/api/webhooks/{int(webhook)}/{token}"


@dataclasses.dataclass
class WebhookLink(hikari.ExecutableWebhook, BaseLink):
    """Represents a link to an incoming webhook.

    The following class methods are used to initialise this:

    * [WebhookLink.from_link][yuyo.links.BaseLink.from_link] to create this
      from a raw webhook link.
    * [WebhookLink.find][yuyo.links.BaseLink.find] to find the first webhook
      link in a string.
    * [WebhookLink.find_iter][yuyo.links.BaseLink.find_iter] to iterate over
      the webhook links in a string.
    """

    __slots__ = ("_app", "_token", "_webhook_id")

    _app: hikari.RESTAware
    _token: str
    _webhook_id: hikari.Snowflake

    _FIND_PATTERN = _MATCH_PATTERN = re.compile(
        r"https?://" + _SUB_DOMAIN + r"discord(?:app)?\.com/api/(?:v\d+/)?webhooks/(\d+)/([^\s/]+)"
    )

    def __str__(self) -> str:
        """Create a raw string representation of this link."""
        return make_webhook_link(self._webhook_id, self._token)

    @property
    def app(self) -> hikari.RESTAware:
        """The bot or REST client this is bound to."""
        return self._app

    @property
    def webhook_id(self) -> hikari.Snowflake:
        """ID of the webhook this links to."""
        return self._webhook_id

    @property
    def token(self) -> str:
        """The webhook's token."""
        return self._token

    @classmethod
    def _from_match(cls, app: hikari.RESTAware, match: re.Match[str], /) -> Self:
        webhook_id, token = match.groups()
        return cls(_app=app, _webhook_id=hikari.Snowflake(webhook_id), _token=token)

    async def fetch_webhook(self) -> hikari.IncomingWebhook:
        """Fetch the incoming webhook this links to.

        Returns
        -------
        hikari.webhooks.IncomingWebhook
            Object of the incoming webhook this links to.

        Raises
        ------
        hikari.errors.UnauthorizedError
            If you are unauthorized to make the request (invalid/missing token).
        hikari.errors.NotFoundError
            If the webhook is not found.
        hikari.errors.RateLimitTooLongError
            Raised in the event that a rate limit occurs that is
            longer than `max_rate_limit` when making a request.
        hikari.errors.InternalServerError
            If an internal error occurs on Discord while handling the request.
        """
        webhook = await self._app.rest.fetch_webhook(self._webhook_id, token=self._token)
        assert isinstance(webhook, hikari.IncomingWebhook)
        return webhook


def make_oauth_link(
    client: hikari.SnowflakeishOr[hikari.PartialApplication],
    scopes: collections.Sequence[typing.Union[hikari.OAuth2Scope, str]],
    /,
    *,
    disable_guild_select: typing.Optional[bool] = None,
    guild: typing.Optional[hikari.SnowflakeishOr[hikari.PartialGuild]] = None,
    permissions: typing.Union[hikari.Permissions, int, None] = None,
    prompt: typing.Optional[str] = None,
    redirect_uri: typing.Optional[str] = None,
    response_type: typing.Optional[str] = None,
    state: typing.Optional[str] = None,
) -> str:
    """Create an Oauth2 authorize link.

    For more information on how Discord's Oauth2 system works see
    <https://discord.com/developers/docs/topics/oauth2>.

    !!! warning
        `response_type` and `redirect_uri` are usually required.

    Parameters
    ----------
    client
        Object or ID of the application this Oauth2 application is for.
    scopes
        The Oauth2 scopes being requested.
    disable_guild_select
        Whether users should be prevented from changing the pre-selected guild.

        This only works properly when `guild` is also passed.
    guild
        Object or ID of a guild to pre-select for the user.

        This is only relevant when the `"bot"` scope is being requested.
    permissions
        The permissions the bot is requesting.

        This is only relevant when the `"bot"` scope is being requested.
    prompt
        How to handles existing authorization.

        For more information see
        <https://discord.com/developers/docs/topics/oauth2#authorization-code-grant-authorization-url-example>.
    redirect_uri
        URI the user should be redirected to with the authorised access
        information.
    response_type
        The type of Oauth2 flow being initiated.

        This will likely either be `"code"` (Authorization Code Grant) or
        `"token"` (Implicit Grant).
    state
        A request-unique state generated for security purposes.

        For more information see
        <https://discord.com/developers/docs/topics/oauth2#state-and-security>.

    Returns
    -------
    str
        The created Oauth2 authorize link.
    """
    query_params: dict[str, typing.Union[str, int]] = {"client_id": int(client), "scope": " ".join(scopes)}

    if disable_guild_select is not None:
        query_params["disable_guild_select"] = str(disable_guild_select).lower()

    if guild is not None:
        query_params["guild_id"] = int(guild)

    if permissions is not None:
        query_params["permissions"] = int(permissions)

    if prompt is not None:
        query_params["prompt"] = prompt

    if redirect_uri is not None:
        query_params["redirect_uri"] = redirect_uri

    if response_type is not None:
        query_params["response_type"] = response_type

    if state is not None:
        query_params["state"] = state

    return f"{hikari.urls.BASE_URL}/api/oauth2/authorize?{urllib.parse.urlencode(query_params)}"


def make_bot_invite(
    client: hikari.SnowflakeishOr[hikari.PartialApplication],
    /,
    *,
    disable_guild_select: typing.Optional[bool] = None,
    guild: typing.Optional[hikari.SnowflakeishOr[hikari.PartialGuild]] = None,
    permissions: typing.Union[hikari.Permissions, int, None] = hikari.Permissions.NONE,
) -> str:
    """Create a Bot invite url.

    Parameters
    ----------
    client
        Object or ID of the application to make an invite link for.
    disable_guild_select
        Whether users should be prevented from changing the pre-selected guild.

        This only works properly when `guild` is also passed.
    guild
        Object or ID of a guild to pre-select for the user.
    permissions
        The permissions the bot is requesting.

        Defaults to requesting a role with no permissions.

        Passing [None][] here will lead to no role being created for the bot.

    Returns
    -------
    str
        The created bot invite.
    """
    return make_oauth_link(
        client,
        [hikari.OAuth2Scope.BOT],
        disable_guild_select=disable_guild_select,
        guild=guild,
        permissions=permissions,
    )
