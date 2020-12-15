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

__all__: typing.Sequence[str] = ["CachedREST"]

import datetime
import time
import typing

from hikari import channels
from hikari import snowflakes

if typing.TYPE_CHECKING:
    from hikari import emojis
    from hikari import guilds
    from hikari import invites
    from hikari import messages
    from hikari import traits
    from hikari import users


KeyT = typing.TypeVar("KeyT")
ValueT = typing.TypeVar("ValueT")


class TimeLimitedMapping(typing.MutableMapping[KeyT, ValueT]):
    __slots__: typing.Sequence[str] = ("_data", "_expiry")

    def __init__(self, *, expire_delta: datetime.timedelta) -> None:
        self._data: typing.Dict[KeyT, typing.Tuple[float, ValueT]] = {}
        self._expiry = expire_delta.total_seconds()

    def __delitem__(self, key: KeyT, /) -> None:
        del self._data[key]
        self.gc()

    def __getitem__(self, key: KeyT, /) -> ValueT:
        return self._data[key][1]

    def __iter__(self) -> typing.Iterator[KeyT]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __setitem__(self, key: KeyT, value: ValueT, /) -> None:
        self.gc()

        # Seeing as we rely on insertion order in _garbage_collect, we have to make sure that each item is added to
        # the end of the dict.
        if key in self:
            del self[key]

        self._data[key] = (time.perf_counter(), value)

    def clear(self) -> None:
        self._data.clear()

    def copy(self) -> typing.Dict[KeyT, ValueT]:
        return {key: value for key, (_, value) in self._data.items()}

    def gc(self) -> None:
        current_time = time.perf_counter()
        for key, value in self._data.copy().items():
            if current_time - value[0] < self._expiry:
                break

            del self._data[key]


class CachedREST:
    # TODO: add guild relation tracking for get view methods
    __slots__: typing.Sequence[str] = (
        "_cache",
        "_channel_store",
        "_emoji_store",
        "_guild_store",
        "_invite_store",
        "_me_state",
        "_me_expire",
        "_me_state_time",
        "_member_store",
        "_message_store",
        "_rest",
        "_role_store",
        "_user_store",
    )

    _channel_store: TimeLimitedMapping[snowflakes.Snowflake, channels.PartialChannel]
    _emoji_store: TimeLimitedMapping[snowflakes.Snowflake, emojis.KnownCustomEmoji]
    _guild_store: TimeLimitedMapping[snowflakes.Snowflake, guilds.Guild]
    _invite_store: TimeLimitedMapping[str, invites.Invite]
    _member_store: TimeLimitedMapping[str, guilds.Member]
    _message_store: TimeLimitedMapping[snowflakes.Snowflake, messages.Message]
    _role_store: TimeLimitedMapping[snowflakes.Snowflake, guilds.Role]
    _user_store: TimeLimitedMapping[snowflakes.Snowflake, users.User]

    def __init__(
        self,
        rest: traits.RESTAware,
        cache: typing.Optional[traits.CacheAware] = None,
        /,
        *,
        channel_expire: datetime.timedelta = datetime.timedelta(seconds=10),
        emoji_expire: datetime.timedelta = datetime.timedelta(seconds=60),
        guild_expire: datetime.timedelta = datetime.timedelta(seconds=30),
        invite_expire: datetime.timedelta = datetime.timedelta(seconds=60),
        me_expire: datetime.timedelta = datetime.timedelta(seconds=120),
        member_expire: datetime.timedelta = datetime.timedelta(seconds=5),
        message_expire: datetime.timedelta = datetime.timedelta(seconds=10),
        role_expire: datetime.timedelta = datetime.timedelta(seconds=10),
        user_expire: datetime.timedelta = datetime.timedelta(seconds=60),
    ) -> None:
        if cache is None and isinstance(rest, traits.CacheAware):
            cache = rest
        # TODO: log that this is running without hikari's cache if cache is left as None

        self._cache = cache
        self._emoji_store = TimeLimitedMapping(expire_delta=emoji_expire)
        self._channel_store = TimeLimitedMapping(expire_delta=channel_expire)
        self._guild_store = TimeLimitedMapping(expire_delta=guild_expire)
        self._invite_store = TimeLimitedMapping(expire_delta=invite_expire)
        self._me_state: typing.Optional[users.OwnUser] = None
        self._me_expire = me_expire.total_seconds()
        self._me_state_time: float = 0.0
        self._member_store = TimeLimitedMapping(expire_delta=member_expire)
        self._message_store = TimeLimitedMapping(expire_delta=message_expire)
        self._rest = rest
        self._role_store = TimeLimitedMapping(expire_delta=role_expire)
        self._user_store = TimeLimitedMapping(expire_delta=user_expire)

    def clear(self) -> None:
        self._channel_store.clear()
        self._emoji_store.clear()
        self._guild_store.clear()
        self._invite_store.clear()
        self._me_state = None
        self._member_store.clear()
        self._message_store.clear()
        self._role_store.clear()
        self._user_store.clear()

    def gc(self) -> None:
        self._channel_store.gc()
        self._emoji_store.gc()
        self._guild_store.gc()
        self._invite_store.gc()

        if self._me_store_is_old():
            self._me_state = None

        self._member_store.gc()
        self._message_store.gc()
        self._role_store.gc()
        self._user_store.gc()

    async def fetch_channel(
        self, channel: snowflakes.SnowflakeishOr[channels.PartialChannel], /
    ) -> channels.PartialChannel:
        channel = snowflakes.Snowflake(channel)
        self._channel_store.gc()
        cached_channel = (self._cache and self._cache.cache.get_guild_channel(channel)) or self._channel_store.get(
            channel
        )
        if cached_channel:
            return cached_channel

        rest_channel = await self._rest.rest.fetch_channel(channel)
        self._channel_store[channel] = rest_channel

        if isinstance(rest_channel, channels.DMChannel):
            self._user_store[rest_channel.recipient.id] = rest_channel.recipient

        elif isinstance(rest_channel, channels.GroupDMChannel):
            self._user_store.update(rest_channel.recipients)

        return rest_channel

    async def fetch_emoji(
        self,
        guild: snowflakes.SnowflakeishOr[guilds.PartialGuild],
        emoji: snowflakes.SnowflakeishOr[emojis.CustomEmoji],
        /,
    ) -> emojis.KnownCustomEmoji:
        emoji = snowflakes.Snowflake(emoji)
        self._emoji_store.gc()

        cached_emoji = (self._cache and self._cache.cache.get_emoji(emoji)) or self._emoji_store.get(emoji)
        if cached_emoji:
            return cached_emoji

        rest_emoji = await self._rest.rest.fetch_emoji(guild, emoji)
        self._emoji_store[emoji] = rest_emoji

        if rest_emoji.user:
            self._user_store[rest_emoji.user.id] = rest_emoji.user

        return rest_emoji

    async def fetch_guild(self, guild: snowflakes.SnowflakeishOr[guilds.PartialGuild], /) -> guilds.Guild:
        guild = snowflakes.Snowflake(guild)
        self._guild_store.gc()

        cached_guild = (self._cache and self._cache.cache.get_available_guild(guild)) or self._guild_store.get(guild)
        if cached_guild:
            return cached_guild

        rest_guild = await self._rest.rest.fetch_guild(guild)
        self._guild_store[guild] = rest_guild
        self._emoji_store.update(rest_guild.emojis)
        self._role_store.update(rest_guild.roles)
        return rest_guild

    async def fetch_invite(self, invite: typing.Union[str, invites.Invite], /) -> invites.Invite:
        invite_code = invite if isinstance(invite, str) else invite.code
        self._invite_store.gc()

        cached_invite = (self._cache and self._cache.cache.get_invite(invite_code)) or self._invite_store.get(
            invite_code
        )
        if cached_invite:
            return cached_invite

        invite = await self._rest.rest.fetch_invite(invite_code)
        self._invite_store[invite_code] = invite

        if invite.target_user:
            self._user_store[invite.target_user.id] = invite.target_user

        if invite.inviter:
            self._user_store[invite.inviter.id] = invite.inviter

        return invite

    def _me_store_is_old(self) -> bool:
        return time.perf_counter() - self._me_state_time >= self._me_expire

    async def fetch_me(self) -> users.OwnUser:
        if self._cache and (cached_user := self._cache.cache.get_me()):
            return cached_user

        if self._me_state and not self._me_store_is_old():
            return self._me_state

        self._me_state = await self._rest.rest.fetch_my_user()
        self._user_store[self._me_state.id] = self._me_state
        self._me_state_time = time.perf_counter()
        return self._me_state

    async def fetch_member(
        self,
        guild: snowflakes.SnowflakeishOr[guilds.PartialGuild],
        user: snowflakes.SnowflakeishOr[users.User],
        /,
    ) -> guilds.Member:
        guild = snowflakes.Snowflake(guild)
        user = snowflakes.Snowflake(user)
        cache_id = f"{guild}:{user}"
        self._member_store.gc()

        cached_member = (self._cache and self._cache.cache.get_member(guild, user)) or self._member_store.get(cache_id)
        if cached_member:
            return cached_member

        rest_member = await self._rest.rest.fetch_member(guild, user)
        self._member_store[cache_id] = rest_member
        self._user_store[user] = rest_member.user
        return rest_member

    async def fetch_message(
        self,
        channel: snowflakes.SnowflakeishOr[channels.PartialChannel],
        message: snowflakes.SnowflakeishOr[messages.Message],
        /,
    ) -> messages.Message:
        channel = snowflakes.Snowflake(channel)
        message = snowflakes.Snowflake(message)
        self._message_store.gc()

        cached_message = (self._cache and self._cache.cache.get_message(message)) or self._message_store.get(message)
        if cached_message:
            return cached_message

        rest_messages = await self._rest.rest.fetch_message(channel, message)
        self._message_store[message] = rest_messages
        return rest_messages

    async def fetch_role(
        self,
        guild: snowflakes.SnowflakeishOr[guilds.PartialGuild],
        role: snowflakes.SnowflakeishOr[guilds.PartialRole],
        /,
    ) -> guilds.Role:
        role = snowflakes.Snowflake(role)
        self._role_store.gc()

        cached_role = (self._cache and self._cache.cache.get_role(role)) or self._role_store.get(role)
        if cached_role:
            return cached_role

        rest_roles = await self._rest.rest.fetch_roles(guild)
        self._role_store.update((role.id, role) for role in rest_roles)

        if role in self._role_store:
            return self._role_store[role]

        raise LookupError("Couldn't find role")  # TODO: this is shit

    async def fetch_user(self, user: snowflakes.SnowflakeishOr[users.User]) -> users.User:
        user = snowflakes.Snowflake(user)
        self._user_store.gc()

        cached_user = (self._cache and self._cache.cache.get_user(user)) or self._user_store.get(user)
        if cached_user:
            return cached_user

        # A special case for if they try to get the current bot's user.
        if self._me_state and user == self._me_state.id and not self._me_store_is_old():
            return self._me_state

        rest_user = await self._rest.rest.fetch_user(user)
        self._user_store[user] = rest_user
        return rest_user
