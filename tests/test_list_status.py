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
# pyright: reportPrivateUsage=none

import datetime
import typing
from unittest import mock

import hikari
import pytest

from yuyo import list_status


class TestCacheStrategy:
    def test_is_shard_bound_property(self):
        assert list_status.CacheStrategy(mock.Mock()).is_shard_bound is True

    @pytest.mark.asyncio()
    async def test_close(self):
        await list_status.CacheStrategy(mock.Mock()).close()

    @pytest.mark.asyncio()
    async def test_open(self):
        await list_status.CacheStrategy(mock.Mock()).open()

    @pytest.mark.asyncio()
    async def test_count(self):
        mock_cache = mock.Mock()
        mock_cache.get_guilds_view.return_value.__len__ = mock.Mock(return_value=4321)
        strategy = list_status.CacheStrategy(mock_cache)

        assert await strategy.count() == 4321

    def test_spawn(self):
        mock_cache = mock.Mock()
        mock_cache.settings = hikari.impl.CacheSettings(
            components=hikari.api.CacheComponents.GUILDS
            | hikari.api.CacheComponents.GUILD_CHANNELS
            | hikari.api.CacheComponents.MEMBERS
        )
        mock_shard = mock.AsyncMock(
            intents=hikari.Intents.GUILDS | hikari.Intents.MESSAGE_CONTENT | hikari.Intents.ALL_MESSAGES
        )

        manager = list_status.ServiceManager(mock.AsyncMock(), cache=mock_cache, shards=mock_shard)

        result = list_status.CacheStrategy.spawn(manager)

        assert isinstance(result, list_status.CacheStrategy)
        assert result._cache == mock_cache

    def test_spawn_when_no_cache(self):
        manager = list_status.ServiceManager(mock.AsyncMock(), shards=mock.AsyncMock(), strategy=mock.AsyncMock())

        with pytest.raises(list_status._InvalidStrategyError):
            list_status.CacheStrategy.spawn(manager)

    def test_spawn_when_no_shards(self):
        manager = list_status.ServiceManager(
            mock.AsyncMock(), cache=mock.Mock(), strategy=mock.AsyncMock(is_shard_bound=False)
        )

        with pytest.raises(list_status._InvalidStrategyError):
            list_status.CacheStrategy.spawn(manager)

    def test_spawn_when_missing_cache_components(self):
        mock_cache = mock.Mock()
        mock_cache.settings = hikari.impl.CacheSettings(
            components=hikari.api.CacheComponents.ALL & ~hikari.api.CacheComponents.GUILDS
        )
        mock_shard = mock.AsyncMock(
            intents=hikari.Intents.GUILDS | hikari.Intents.MESSAGE_CONTENT | hikari.Intents.ALL_MESSAGES
        )

        manager = list_status.ServiceManager(
            mock.AsyncMock(), cache=mock_cache, shards=mock_shard, strategy=mock.AsyncMock()
        )

        with pytest.raises(list_status._InvalidStrategyError):
            list_status.CacheStrategy.spawn(manager)

    def test_spawn_when_missing_intent(self):
        mock_cache = mock.Mock()
        mock_cache.settings = hikari.impl.CacheSettings(
            components=hikari.api.CacheComponents.GUILDS
            | hikari.api.CacheComponents.GUILD_CHANNELS
            | hikari.api.CacheComponents.MEMBERS
        )
        mock_shard = mock.AsyncMock(intents=hikari.Intents.ALL & ~hikari.Intents.GUILDS)

        manager = list_status.ServiceManager(
            mock.AsyncMock(), cache=mock_cache, shards=mock_shard, strategy=mock.AsyncMock()
        )

        with pytest.raises(list_status._InvalidStrategyError):
            list_status.CacheStrategy.spawn(manager)


class TestSakeStrategy:
    def test_is_shard_bound_property(self):
        assert list_status.SakeStrategy(mock.AsyncMock()).is_shard_bound is False

    @pytest.mark.asyncio()
    async def test_close(self):
        await list_status.SakeStrategy(mock.AsyncMock()).close()

    @pytest.mark.asyncio()
    async def test_open(self):
        await list_status.SakeStrategy(mock.AsyncMock()).open()

    @pytest.mark.asyncio()
    async def test_count(self):
        mock_cache = mock.Mock()
        mock_cache.iter_guilds.return_value.len = mock.AsyncMock()
        strategy = list_status.SakeStrategy(mock_cache)

        assert await strategy.count() is mock_cache.iter_guilds.return_value.len.return_value

    @pytest.mark.asyncio()
    async def test_count_when_iter_raises_closed_client(self):
        import sake

        mock_cache = mock.Mock()
        mock_cache.iter_guilds.return_value.len = mock.AsyncMock(side_effect=sake.ClosedClient("meow"))
        strategy = list_status.SakeStrategy(mock_cache)

        with pytest.raises(list_status.CountUnknownError):
            await strategy.count()


class TestEventStrategy:
    def test_is_shard_bound_property(self):
        assert list_status.EventStrategy(mock.Mock(), mock.AsyncMock()).is_shard_bound is True

    @pytest.mark.parametrize(
        ("error_on", "error"),
        [
            (0, ValueError),
            (0, LookupError),
            (1, ValueError),
            (1, LookupError),
            (2, ValueError),
            (2, LookupError),
            (3, ValueError),
            (3, LookupError),
            (4, ValueError),
            (4, LookupError),
        ],
    )
    @pytest.mark.asyncio()
    async def test_close_when_any_event_listener_not_registered(self, error_on: int, error: typing.Type[Exception]):
        mock_event_manager = mock.Mock()
        mock_event_manager.unsubscribe.side_effect = [None] * error_on + [error] + [None] * (4 - error_on)
        strategy = list_status.EventStrategy(mock_event_manager, mock.AsyncMock())
        await strategy.open()

        await strategy.close()

    @pytest.mark.asyncio()
    async def test_close_when_already_closed(self):
        mock_event_manager = mock.Mock()
        strategy = list_status.EventStrategy(mock_event_manager, mock.AsyncMock())

        await strategy.close()

        mock_event_manager.unsubscribe.close.assert_not_called()

    @pytest.mark.asyncio()
    async def test_open_when_already_open(self):
        mock_event_manager = mock.Mock()
        strategy = list_status.EventStrategy(mock_event_manager, mock.AsyncMock())
        await strategy.open()
        mock_event_manager.subscribe.reset_mock()

        await strategy.open()

        mock_event_manager.subscribe.close.assert_not_called()

    @pytest.mark.asyncio()
    async def test_count_after_shard_readies(self):
        event = hikari.ShardReadyEvent(
            shard=mock.AsyncMock(),
            actual_gateway_version=10,
            resume_gateway_url="yeet",
            session_id="meow",
            my_user=mock.Mock(),
            unavailable_guilds=[],
            application_id=hikari.Snowflake(54123),
            application_flags=hikari.ApplicationFlags(0),
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        strategy = list_status.EventStrategy(event_manager, mock.AsyncMock())
        await strategy.open()

        event.unavailable_guilds = [
            hikari.Snowflake(634234),
            hikari.Snowflake(65234123),
            hikari.Snowflake(876547234),
            hikari.Snowflake(634234),
            hikari.Snowflake(887643234),
            hikari.Snowflake(123),
            hikari.Snowflake(44532134),
        ]
        await event_manager.dispatch(event)
        event.unavailable_guilds = [
            hikari.Snowflake(65423487456),
            hikari.Snowflake(342765432),
            hikari.Snowflake(234654134),
            hikari.Snowflake(634234),
            hikari.Snowflake(887643234),
            hikari.Snowflake(435234765),
            hikari.Snowflake(44532134),
        ]
        await event_manager.dispatch(event)

        assert await strategy.count() == 10

    @pytest.mark.asyncio()
    async def test_count_after_guild_available_event_for_known_guild(self):
        event = hikari.GuildAvailableEvent(
            shard=mock.AsyncMock(),
            guild=mock.Mock(id=hikari.Snowflake(45123123)),
            emojis={},
            stickers={},
            roles={},
            channels={},
            threads={},
            members={},
            presences={},
            voice_states={},
            chunk_nonce=None,
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        strategy = list_status.EventStrategy(event_manager, mock.AsyncMock())
        await strategy.open()

        await event_manager.dispatch(event)
        await event_manager.dispatch(event)

        assert await strategy.count() == 1

    @pytest.mark.asyncio()
    async def test_count_after_guild_available_event_for_unknown_guild(self):
        event = hikari.GuildAvailableEvent(
            shard=mock.AsyncMock(),
            guild=mock.Mock(id=hikari.Snowflake(45123123)),
            emojis={},
            stickers={},
            roles={},
            channels={},
            threads={},
            members={},
            presences={},
            voice_states={},
            chunk_nonce=None,
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        strategy = list_status.EventStrategy(event_manager, mock.AsyncMock())
        await strategy.open()

        await event_manager.dispatch(event)
        event.guild.id = hikari.Snowflake(546534)
        await event_manager.dispatch(event)

        assert await strategy.count() == 2

    @pytest.mark.asyncio()
    async def test_count_after_guild_leave_event_for_known_guild(self):
        available_event = hikari.GuildAvailableEvent(
            shard=mock.AsyncMock(),
            guild=mock.Mock(id=hikari.Snowflake(45123123)),
            emojis={},
            stickers={},
            roles={},
            channels={},
            threads={},
            members={},
            presences={},
            voice_states={},
            chunk_nonce=None,
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        strategy = list_status.EventStrategy(event_manager, mock.AsyncMock())
        await strategy.open()
        await event_manager.dispatch(available_event)
        available_event.guild.id = hikari.Snowflake(546534)
        await event_manager.dispatch(available_event)

        leave_event = hikari.GuildLeaveEvent(
            app=mock.AsyncMock(), shard=mock.AsyncMock(), guild_id=hikari.Snowflake(546534), old_guild=None
        )
        await event_manager.dispatch(leave_event)

        assert await strategy.count() == 1

    @pytest.mark.asyncio()
    async def test_count_after_guild_leave_event_for_unknown_guild(self):
        available_event = hikari.GuildAvailableEvent(
            shard=mock.AsyncMock(),
            guild=mock.Mock(id=hikari.Snowflake(12345123)),
            emojis={},
            stickers={},
            roles={},
            channels={},
            threads={},
            members={},
            presences={},
            voice_states={},
            chunk_nonce=None,
        )
        leave_event = hikari.GuildLeaveEvent(
            app=mock.AsyncMock(), shard=mock.AsyncMock(), guild_id=hikari.Snowflake(32154334), old_guild=None
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        strategy = list_status.EventStrategy(event_manager, mock.AsyncMock())
        await strategy.open()
        await event_manager.dispatch(available_event)

        await event_manager.dispatch(leave_event)
        leave_event.guild_id = hikari.Snowflake(3412123)
        await event_manager.dispatch(leave_event)

        assert await strategy.count() == 1

    @pytest.mark.asyncio()
    async def test_count_after_guild_update_event_for_known_guild(self):
        guild_update_event = hikari.GuildUpdateEvent(
            shard=mock.AsyncMock(), old_guild=None, guild=mock.Mock(id=123342123), emojis={}, stickers={}, roles={}
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        strategy = list_status.EventStrategy(event_manager, mock.AsyncMock())
        await strategy.open()
        await event_manager.dispatch(guild_update_event)

        await event_manager.dispatch(guild_update_event)

        assert await strategy.count() == 1

    @pytest.mark.asyncio()
    async def test_count_after_guild_update_event_for_unknown_guild(self):
        guild_update_event = hikari.GuildUpdateEvent(
            shard=mock.AsyncMock(), old_guild=None, guild=mock.Mock(id=123342123), emojis={}, stickers={}, roles={}
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        strategy = list_status.EventStrategy(event_manager, mock.AsyncMock())
        await strategy.open()

        await event_manager.dispatch(guild_update_event)
        guild_update_event.guild.id = hikari.Snowflake(541231)
        await event_manager.dispatch(guild_update_event)

        assert await strategy.count() == 2

    @pytest.mark.asyncio()
    async def test_count_after_starting_event(self):
        ready_event = hikari.ShardReadyEvent(
            shard=mock.AsyncMock(),
            actual_gateway_version=10,
            resume_gateway_url="yeet",
            session_id="meow",
            my_user=mock.Mock(),
            unavailable_guilds=[hikari.Snowflake(5642134), hikari.Snowflake(4123321)],
            application_id=hikari.Snowflake(54123),
            application_flags=hikari.ApplicationFlags(0),
        )
        guild_available_event = hikari.GuildAvailableEvent(
            shard=mock.AsyncMock(),
            guild=mock.Mock(id=hikari.Snowflake(45123123)),
            emojis={},
            stickers={},
            roles={},
            channels={},
            threads={},
            members={},
            presences={},
            voice_states={},
            chunk_nonce=None,
        )
        guild_update_event = hikari.GuildUpdateEvent(
            shard=mock.AsyncMock(), old_guild=None, guild=mock.Mock(id=123342123), emojis={}, stickers={}, roles={}
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        strategy = list_status.EventStrategy(event_manager, mock.AsyncMock())
        await strategy.open()
        await event_manager.dispatch(ready_event)
        await event_manager.dispatch(guild_available_event)
        await event_manager.dispatch(guild_update_event)
        assert await strategy.count() == 4

        await event_manager.dispatch(hikari.StartingEvent(app=mock.AsyncMock()))

        assert await strategy.count() == 0

        await event_manager.dispatch(ready_event)
        await event_manager.dispatch(guild_available_event)
        await event_manager.dispatch(guild_update_event)

        assert await strategy.count() == 4

    @pytest.mark.asyncio()
    async def test_count_after_close(self):
        ready_event = hikari.ShardReadyEvent(
            shard=mock.AsyncMock(),
            actual_gateway_version=10,
            resume_gateway_url="yeet",
            session_id="meow",
            my_user=mock.Mock(),
            unavailable_guilds=[hikari.Snowflake(5642134), hikari.Snowflake(4123321)],
            application_id=hikari.Snowflake(54123),
            application_flags=hikari.ApplicationFlags(0),
        )
        guild_available_event = hikari.GuildAvailableEvent(
            shard=mock.AsyncMock(),
            guild=mock.Mock(id=hikari.Snowflake(45123123)),
            emojis={},
            stickers={},
            roles={},
            channels={},
            threads={},
            members={},
            presences={},
            voice_states={},
            chunk_nonce=None,
        )
        guild_update_event = hikari.GuildUpdateEvent(
            shard=mock.AsyncMock(), old_guild=None, guild=mock.Mock(id=123342123), emojis={}, stickers={}, roles={}
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        strategy = list_status.EventStrategy(event_manager, mock.AsyncMock())
        await strategy.open()
        await event_manager.dispatch(ready_event)
        await event_manager.dispatch(guild_available_event)
        await event_manager.dispatch(guild_update_event)
        assert await strategy.count() == 4

        await strategy.close()

        assert await strategy.count() == 0

        await event_manager.dispatch(ready_event)
        await event_manager.dispatch(guild_available_event)
        await event_manager.dispatch(guild_update_event)

        assert await strategy.count() == 0

    def test_spawn(self):
        mock_manager = mock.Mock()
        mock_shards = mock.AsyncMock(
            intents=hikari.Intents.GUILDS | hikari.Intents.MESSAGE_CONTENT | hikari.Intents.GUILD_WEBHOOKS
        )
        manager = list_status.ServiceManager(
            mock.AsyncMock(), event_manager=mock_manager, shards=mock_shards, strategy=mock.AsyncMock()
        )

        result = list_status.EventStrategy.spawn(manager)

        assert isinstance(result, list_status.EventStrategy)
        assert result._event_manager is mock_manager
        assert result._shards is mock_shards

    def test_spawn_when_no_event_manager(self):
        mock_shards = mock.AsyncMock(
            intents=hikari.Intents.GUILDS | hikari.Intents.MESSAGE_CONTENT | hikari.Intents.GUILD_WEBHOOKS
        )
        manager = list_status.ServiceManager(mock.AsyncMock(), shards=mock_shards, strategy=mock.AsyncMock())

        with pytest.raises(list_status._InvalidStrategyError):
            list_status.EventStrategy.spawn(manager)

    def test_spawn_when_no_shards(self):
        manager = list_status.ServiceManager(
            mock.AsyncMock(), event_manager=mock.Mock(), strategy=mock.AsyncMock(is_shard_bound=False)
        )

        with pytest.raises(list_status._InvalidStrategyError):
            list_status.EventStrategy.spawn(manager)

    def test_spawn_when_missing_intent(self):
        mock_shards = mock.AsyncMock(intents=hikari.Intents.ALL & ~hikari.Intents.GUILDS)
        manager = list_status.ServiceManager(mock.AsyncMock(), shards=mock_shards, strategy=mock.AsyncMock())

        with pytest.raises(list_status._InvalidStrategyError):
            list_status.EventStrategy.spawn(manager)


class TestServiceManager:
    @pytest.mark.skip(reason="TODO")
    def test_init(self):
        ...

    def test_from_gateway_bot(self):
        mock_counter = mock.AsyncMock()
        mock_bot = mock.AsyncMock(event_manager=mock.Mock())

        manager = list_status.ServiceManager.from_gateway_bot(mock_bot, user_agent="yeet yeet", strategy=mock_counter)

        assert manager.counter is mock_counter
        assert manager.rest is mock_bot.rest
        assert manager.cache is mock_bot.cache
        assert manager.shards is mock_bot
        assert manager.user_agent == "yeet yeet"
        mock_bot.event_manager.subscribe.assert_called()

    def test_from_gateway_bot_when_only_bot(self):
        mock_bot = mock.AsyncMock(event_manager=mock.Mock())

        manager = list_status.ServiceManager.from_gateway_bot(mock_bot, event_managed=False)

        assert manager.user_agent == "Yuyo.last_status"
        mock_bot.event_manager.subscribe.assert_not_called()

    def test_is_alive_property(self):
        manager = list_status.ServiceManager(mock.AsyncMock(), strategy=mock.AsyncMock(is_shard_bound=False))

        assert manager.is_alive is False

    def test_counter_property(self):
        mock_counter = mock.AsyncMock(is_shard_bound=False)
        manager = list_status.ServiceManager(mock.AsyncMock(), strategy=mock_counter)

        assert manager.counter is mock_counter

    def test_event_manager_property(self):
        mock_event_manager = mock.Mock()
        manager = list_status.ServiceManager(
            mock.AsyncMock(), event_manager=mock_event_manager, strategy=mock.AsyncMock(is_shard_bound=False)
        )

        assert manager.event_manager is mock_event_manager

    def test_add_service(self):
        manager = list_status.ServiceManager(mock.AsyncMock(), strategy=mock.AsyncMock(is_shard_bound=False))
        mock_service_1 = mock.AsyncMock()
        mock_service_2 = mock.AsyncMock()
        mock_service_3 = mock.AsyncMock()
        mock_service_4 = mock.AsyncMock()

        manager.add_service(mock_service_1, repeat=43122).add_service(
            mock_service_2, repeat=datetime.timedelta(seconds=43125)
        ).add_service(mock_service_3, repeat=23.321).add_service(mock_service_4)

        assert manager.services == [mock_service_3, mock_service_4, mock_service_1, mock_service_2]

    def test_remove_service(self):
        mock_service_1 = mock.AsyncMock()
        mock_service_2 = mock.AsyncMock()
        manager = (
            list_status.ServiceManager(mock.AsyncMock(), strategy=mock.AsyncMock(is_shard_bound=False))
            .add_service(mock_service_1, repeat=43123)
            .add_service(mock_service_2)
        )

        assert manager.services == [mock_service_2, mock_service_1]

    def test_with_service(self):
        mock_service_1 = mock.AsyncMock()
        mock_service_2 = mock.AsyncMock()
        manager = (
            list_status.ServiceManager(mock.AsyncMock(), strategy=mock.AsyncMock(is_shard_bound=False))
            .add_service(mock_service_1, repeat=43123)
            .add_service(mock_service_2)
        )

        @manager.with_service(repeat=1233122)
        async def decorated_service_1(_: list_status.AbstractManager):
            ...

        @manager.with_service(repeat=123.321)
        async def decorated_service_2(_: list_status.AbstractManager):
            ...

        @manager.with_service(repeat=datetime.timedelta(seconds=56543))
        async def decorated_service_3(_: list_status.AbstractManager):
            ...

        @manager.with_service()
        async def decorated_service_4(_: list_status.AbstractManager):
            ...

        assert manager.services == [
            decorated_service_2,
            mock_service_2,
            decorated_service_4,
            mock_service_1,
            decorated_service_3,
            decorated_service_1,
        ]

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_open(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_close(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_get_me(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_get_session(self):
        ...


@pytest.mark.skip(reason="TODO")
class TestTopGGService:
    ...


@pytest.mark.skip(reason="TODO")
class TestBotsGGService:
    ...


@pytest.mark.skip(reason="TODO")
class TestDiscordBotListService:
    ...
