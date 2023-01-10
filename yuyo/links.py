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
    "InviteLink",
    "MessageLink",
    "TemplateLink",
    "WebhookLink",
    "make_invite_link",
    "make_message_link",
    "make_template_link",
    "make_webhook_link",
]

import dataclasses
import re
import typing

import hikari
import hikari.urls

if typing.TYPE_CHECKING:
    from collections import abc as collections

    from typing_extensions import Self


def make_invite_link(invite: typing.Union[str, hikari.InviteCode], /) -> str:
    """Make a raw link for an invite.

    Parameters
    ----------
    invite_code
        Object or string codw of the invite to make a raw link for.

    Returns
    -------
    str
        The raw invite link.
    """
    invite_code = invite.code if isinstance(invite, hikari.InviteCode) else invite
    return f"https://discord.gg/{invite_code}"


_INVITE_PATTERN = re.compile(r"https://(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/(\w+)")


@dataclasses.dataclass
class InviteLink(hikari.InviteCode):
    """Represents a link to a Discord invite.

    These should be created using [InviteLink.from_link][InviteLink.links.InviteLink.from_link],
    [InviteLink.find][yuyo.links.InviteLink.find], or
    [InviteLink.find_iter][yuyo.links.InviteLink.find_iter].
    """

    __slots__ = ("_app", "_code")

    _app: hikari.RESTAware
    _code: str

    @classmethod
    def find(cls, app: hikari.RESTAware, content: str, /) -> typing.Optional[Self]:
        """Find the first invite link in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        Self | None
            The found invite link or [None][].
        """
        if result := next(cls.find_iter(app, content), None):
            return result

        return None  # MyPy compat

    @classmethod
    def find_iter(cls, app: hikari.RESTAware, content: str, /) -> collections.Iterator[Self]:
        """Iterate over the invite links in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        collections.abc.Iterator[Self]
            Iterator of the invite links in a invite.
        """
        for match in _INVITE_PATTERN.finditer(content):
            yield cls._from_match(app, match)

    @classmethod
    def from_link(cls, app: hikari.RESTAware, link: str, /) -> Self:
        """Create a [InviteLink][yuyo.links.InviteLink] from a raw link.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        link
            The string link to use.

        Returns
        -------
        Self
            The created invite link.

        Raises
        ------
        ValueError
            If the string doesn't match the expected invite link format.
        """
        if match := _INVITE_PATTERN.fullmatch(link.strip()):
            return cls._from_match(app, match)

        raise ValueError("Link doesn't match pattern")

    @classmethod
    def _from_match(cls, app: hikari.RESTAware, match: re.Match[str], /) -> Self:
        return cls(_app=app, _code=match.group())

    @property
    def code(self) -> str:
        """The invite's code."""
        return self._code

    async def fetch(self) -> hikari.Invite:
        return await self._app.rest.fetch_invite(self._code)

    def get(self) -> typing.Optional[hikari.InviteWithMetadata]:
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

        If left as [None][] then this will be a DM message link.

    Returns
    -------
    str
        The raw message link.
    """
    guild_ = "@me" if guild is None else int(guild)
    return f"{hikari.urls.BASE_URL}/channels/{guild_}/{int(channel)}/{int(message)}"


_MESSAGE_PATTERN = re.compile(r"https://(?:www\.)?discord(?:app)?\.com/channels/(\d+|@me)/(\d+)/(\d+)")


@dataclasses.dataclass
class MessageLink:
    """Represents a link to a message on Discord.

    These should be created using [MessageLink.from_link][yuyo.links.MessageLink.from_link],
    [MessageLink.find][yuyo.links.MessageLink.find], or
    [MessageLink.find_iter][yuyo.links.MessageLink.find_iter].
    """

    __slots__ = ("_app", "_channel_id", "_guild_id", "_message_id")

    _app: hikari.RESTAware
    _channel_id: hikari.Snowflake
    _guild_id: typing.Optional[hikari.Snowflake]
    _message_id: hikari.Snowflake

    @classmethod
    def find(cls, app: hikari.RESTAware, content: str, /) -> typing.Optional[Self]:
        """Find the first message link in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        Self | None
            The found message link or [None][].
        """
        if result := next(cls.find_iter(app, content), None):
            return result

        return None  # MyPy compat

    @classmethod
    def find_iter(cls, app: hikari.RESTAware, content: str, /) -> collections.Iterator[Self]:
        """Iterate over the message links in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        collections.abc.Iterator[Self]
            Iterator of the message links in a message.
        """
        for match in _MESSAGE_PATTERN.finditer(content):
            yield cls._from_match(app, match)

    @classmethod
    def from_link(cls, app: hikari.RESTAware, link: str, /) -> Self:
        """Create a [MessageLink][yuyo.links.MessageLink] from a raw link.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        link
            The string link to use.

        Returns
        -------
        Self
            The created message link.

        Raises
        ------
        ValueError
            If the string doesn't match the expected message link format.
        """
        if match := _MESSAGE_PATTERN.fullmatch(link.strip()):
            return cls._from_match(app, match)

        raise ValueError("Link doesn't match pattern")

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

    def __str__(self) -> str:
        return make_message_link(self._channel_id, self._message_id, guild=self._guild_id)

    @property
    def channel_id(self) -> hikari.Snowflake:
        """ID of the channel this message is in."""
        return self._channel_id

    @property
    def guild_id(self) -> typing.Optional[hikari.Snowflake]:
        """ID of the guild this message is in.

        Will be [None][] for DM message links.
        """
        return self._guild_id

    @property
    def is_dm_link(self) -> bool:
        """Whether this links to a message in a DM channel."""
        return self._guild_id is None

    @property
    def message_id(self) -> hikari.Snowflake:
        """ID of the message this links to."""
        return self._message_id

    async def fetch(self) -> hikari.Message:
        return await self._app.rest.fetch_message(self._channel_id, self._message_id)

    def get(self) -> typing.Optional[hikari.Message]:
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


_TEMPLATE_PATTERN = re.compile(r"https://(?:www\.)?discord(?:\.new|(?:app)?\.com/template)/(\w+)")


@dataclasses.dataclass
class TemplateLink:
    """Represents a link to a guild template.

    These should be created using [TemplateLink.from_link][yuyo.links.TemplateLink.from_link],
    [TemplateLink.find][yuyo.links.TemplateLink.find], or
    [TemplateLink.find_iter][yuyo.links.TemplateLink.find_iter].
    """

    __slots__ = ("_app", "_code")

    _app: hikari.RESTAware
    _code: str

    @classmethod
    def find(cls, app: hikari.RESTAware, content: str, /) -> typing.Optional[Self]:
        """Find the first template link in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        Self | None
            The found template link or [None][].
        """
        if result := next(cls.find_iter(app, content), None):
            return result

        return None  # MyPy compat

    @classmethod
    def find_iter(cls, app: hikari.RESTAware, content: str, /) -> collections.Iterator[Self]:
        """Iterate over the template links in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        collections.abc.Iterator[Self]
            Iterator of the template links in a message.
        """
        for match in _TEMPLATE_PATTERN.finditer(content):
            yield cls._from_match(app, match)

    @classmethod
    def from_link(cls, app: hikari.RESTAware, link: str, /) -> Self:
        """Create a [TemplateLink][yuyo.links.TemplateLink] from a raw link.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        link
            The string link to use.

        Returns
        -------
        Self
            The created template link.

        Raises
        ------
        ValueError
            If the string doesn't match the expected template link format.
        """
        if match := _TEMPLATE_PATTERN.fullmatch(link.strip()):
            return cls._from_match(app, match)

        raise ValueError("Link doesn't match pattern")

    @classmethod
    def _from_match(cls, app: hikari.RESTAware, match: re.Match[str], /) -> Self:
        return cls(_app=app, _code=match.group())

    def __str__(self) -> str:
        return make_template_link(self._code)

    @property
    def code(self) -> str:
        """The template's code."""
        return self._code

    async def fetch(self) -> hikari.Template:
        return await self._app.rest.fetch_template(self._code)


_WEBHOOK_PATTERN = re.compile(r"https://(?:www\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/(\d+)/([\w\d\.\-]+)")


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
class WebhookLink(hikari.ExecutableWebhook):
    """Represents a link to an incoming webhook.

    These should be created using [WebhookLink.from_link][yuyo.links.WebhookLink.from_link],
    [WebhookLink.find][yuyo.links.WebhookLink.find], or
    [WebhookLink.find_iter][yuyo.links.WebhookLink.find_iter].
    """

    __slots__ = ("_app", "_token", "_webhook_id")

    _app: hikari.RESTAware
    _token: str
    _webhook_id: hikari.Snowflake

    @classmethod
    def find(cls, app: hikari.RESTAware, content: str, /) -> typing.Optional[Self]:
        """Find the first webhook link in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        Self | None
            The found webhook link or [None][].
        """
        if result := next(cls.find_iter(app, content), None):
            return result

        return None  # MyPy compat

    @classmethod
    def find_iter(cls, app: hikari.RESTAware, content: str, /) -> collections.Iterator[Self]:
        """Iterate over the webhook links in a string.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        content
            The string to searh in.

        Returns
        -------
        collections.abc.Iterator[Self]
            Iterator of the webhook links in a message.
        """
        for match in _WEBHOOK_PATTERN.finditer(content):
            yield cls._from_match(app, match)

    @classmethod
    def from_link(cls, app: hikari.RESTAware, link: str, /) -> Self:
        """Create a [WebhookLink][yuyo.links.WebhookLink] from a raw link.

        Parameters
        ----------
        app
            The Hikari bot or REST app this should be bound to.
        link
            The string link to use.

        Returns
        -------
        Self
            The created webhook link.

        Raises
        ------
        ValueError
            If the string doesn't match the expected webhook link format.
        """
        if match := _WEBHOOK_PATTERN.fullmatch(link.strip()):
            return cls._from_match(app, match)

        raise ValueError("Link doesn't match pattern")

    @classmethod
    def _from_match(cls, app: hikari.RESTAware, match: re.Match[str], /) -> Self:
        webhook_id, token = match.groups()
        return cls(_app=app, _webhook_id=hikari.Snowflake(webhook_id), _token=token)

    def __str__(self) -> str:
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

    async def fetch(self) -> hikari.IncomingWebhook:
        webhook = await self._app.rest.fetch_webhook(self._webhook_id, token=self._token)
        assert isinstance(webhook, hikari.IncomingWebhook)
        return webhook
