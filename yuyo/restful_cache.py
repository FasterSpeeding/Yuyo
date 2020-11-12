# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020, Faster Speeding
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
from __future__ import annotations

__slots__: typing.Sequence[str] = ["RestfulCache"]

import typing

from hikari import channels
from hikari import snowflakes

if typing.TYPE_CHECKING:
    from hikari import emojis
    from hikari import guilds
    from hikari import invites
    from hikari import traits
    from hikari import users


class RestfulCache:
    __slots__: typing.Sequence[str] = ("_cache", "_rest")

    def __init__(self, cache: traits.CacheAware, rest: typing.Optional[traits.RESTAware] = None, /) -> None:
        if rest is None and isinstance(cache, traits.RESTAware):
            rest = cache

        if rest is None:
            raise ValueError("REST aware client must be provided")

        self._cache = cache
        self._rest = rest

    async def get_emoji(
        self,
        guild: snowflakes.SnowflakeishOr[guilds.PartialGuild],
        emoji: snowflakes.SnowflakeishOr[emojis.CustomEmoji],
        /,
    ) -> emojis.KnownCustomEmoji:
        emoji = snowflakes.Snowflake(emoji)
        if cached_emoji := self._cache.cache.get_emoji(emoji):
            return cached_emoji

        return await self._rest.rest.fetch_emoji(guild, emoji)

    async def get_guild(self, guild: snowflakes.SnowflakeishOr[guilds.PartialGuild], /) -> guilds.Guild:
        guild = snowflakes.Snowflake(guild)
        if cached_guild := self._cache.cache.get_available_guild(guild):
            return cached_guild

        return await self._rest.rest.fetch_guild(guild)

    async def get_guild_channel(
        self, channel: snowflakes.SnowflakeishOr[channels.PartialChannel], /
    ) -> channels.GuildChannel:
        channel = snowflakes.Snowflake(channel)
        if cached_channel := self._cache.cache.get_guild_channel(channel):
            return cached_channel

        rest_channel = await self._rest.rest.fetch_channel(channel)

        if not isinstance(rest_channel, channels.GuildChannel):
            raise RuntimeError("Received a DM channel.")

        return rest_channel

    async def get_invite(self, invite: typing.Union[str, invites.Invite], /) -> invites.Invite:
        invite_code = invite if isinstance(invite, str) else invite.code
        if cached_invite := self._cache.cache.get_invite(invite_code):
            return cached_invite

        return await self._rest.rest.fetch_invite(invite_code)

    async def get_me(self) -> users.OwnUser:
        if cached_user := self._cache.cache.get_me():
            return cached_user

        return await self._rest.rest.fetch_my_user()

    async def get_member(
        self,
        guild: snowflakes.SnowflakeishOr[guilds.PartialGuild],
        user: snowflakes.SnowflakeishOr[users.User],
        /,
    ) -> guilds.Member:
        guild = snowflakes.Snowflake(guild)
        user = snowflakes.Snowflake(user)
        if cached_member := self._cache.cache.get_member(guild, user):
            return cached_member

        return await self._rest.rest.fetch_member(guild, user)

    async def get_role(
        self,
        guild: snowflakes.SnowflakeishOr[guilds.PartialGuild],
        role: snowflakes.SnowflakeishOr[guilds.PartialRole],
        /,
    ) -> guilds.Role:
        role = snowflakes.Snowflake(role)
        if cached_role := self._cache.cache.get_role(role):
            return cached_role

        return await self._rest.rest.edit_role(guild, role)

    async def get_user(self, user: snowflakes.SnowflakeishOr[users.User]) -> users.User:
        user = snowflakes.Snowflake(user)
        if cached_user := self._cache.cache.get_user(user):
            return cached_user

        return await self._rest.rest.fetch_user(user)
