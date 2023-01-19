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

# pyright: reportPrivateUsage=none
# pyright: reportUnknownMemberType=none
# This leads to too many false-positives around mocks.

import datetime
from unittest import mock

import hikari
import pytest

from yuyo import _internal
from yuyo import list_status


class TestCacheStrategy:
    def test_is_shard_bound_property(self):
        assert list_status.CacheStrategy(mock.Mock(), mock.AsyncMock()).is_shard_bound is True

    @pytest.mark.asyncio()
    async def test_close(self):
        await list_status.CacheStrategy(mock.Mock(), mock.AsyncMock()).close()

    @pytest.mark.asyncio()
    async def test_open(self):
        await list_status.CacheStrategy(mock.Mock(), mock.AsyncMock()).open()

    @pytest.mark.asyncio()
    async def test_count(self):
        mock_cache = mock.Mock()
        mock_cache.get_guilds_view.return_value = {
            342343242301298764: mock.Mock(),
            745924312145647646: mock.Mock(),
            234543645234123132: mock.Mock(),
            45564353434245545: mock.Mock(),
            97645665343455434: mock.Mock(),
        }
        mock_shards = mock.AsyncMock(
            shard_count=8, shards={0: mock.Mock(), 1: mock.Mock(), 2: mock.Mock(), 3: mock.Mock()}
        )
        strategy = list_status.CacheStrategy(mock_cache, mock_shards)

        assert await strategy.count() == {0: 0, 1: 0, 2: 3, 3: 2}

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
    async def test_close_when_any_event_listener_not_registered(self, error_on: int, error: type[Exception]):
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
        mock_shards = mock.AsyncMock(
            shard_count=4, shards={0: mock.Mock(), 1: mock.Mock(), 2: mock.Mock(), 3: mock.Mock()}
        )
        strategy = list_status.EventStrategy(event_manager, mock_shards)
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

        assert await strategy.count() == {0: 3, 1: 1, 2: 2, 3: 4}

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
        mock_shards = mock.AsyncMock(shard_count=2, shards={0: mock.Mock()})
        strategy = list_status.EventStrategy(event_manager, mock_shards)
        await strategy.open()

        await event_manager.dispatch(event)
        await event_manager.dispatch(event)

        assert await strategy.count() == {0: 1}

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
        mock_shards = mock.AsyncMock(shard_count=4, shards={0: mock.Mock(), 1: mock.Mock()})
        strategy = list_status.EventStrategy(event_manager, mock_shards)
        await strategy.open()

        await event_manager.dispatch(event)
        event.guild.id = hikari.Snowflake(546534)
        await event_manager.dispatch(event)

        assert await strategy.count() == {0: 1, 1: 0, 2: 1}

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
        mock_shards = mock.AsyncMock(shard_count=2, shards={0: mock.Mock(), 1: mock.Mock()})
        strategy = list_status.EventStrategy(event_manager, mock_shards)
        await strategy.open()
        await event_manager.dispatch(available_event)
        available_event.guild.id = hikari.Snowflake(546534)
        await event_manager.dispatch(available_event)

        leave_event = hikari.GuildLeaveEvent(
            app=mock.AsyncMock(), shard=mock.AsyncMock(), guild_id=hikari.Snowflake(546534), old_guild=None
        )
        await event_manager.dispatch(leave_event)

        assert await strategy.count() == {0: 1, 1: 0}

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
        mock_shards = mock.AsyncMock(
            shard_count=8, shards={0: mock.Mock(), 1: mock.Mock(), 2: mock.Mock(), 3: mock.Mock()}
        )
        strategy = list_status.EventStrategy(event_manager, mock_shards)
        await strategy.open()
        await event_manager.dispatch(available_event)

        await event_manager.dispatch(leave_event)
        leave_event.guild_id = hikari.Snowflake(3412123)
        await event_manager.dispatch(leave_event)

        assert await strategy.count() == {0: 0, 1: 0, 2: 1, 3: 0}

    @pytest.mark.asyncio()
    async def test_count_after_guild_update_event_for_known_guild(self):
        guild_update_event = hikari.GuildUpdateEvent(
            shard=mock.AsyncMock(), old_guild=None, guild=mock.Mock(id=123342123), emojis={}, stickers={}, roles={}
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        mock_shards = mock.AsyncMock(shard_count=4, shards={1: mock.Mock()})
        strategy = list_status.EventStrategy(event_manager, mock_shards)
        await strategy.open()
        await event_manager.dispatch(guild_update_event)

        await event_manager.dispatch(guild_update_event)

        assert await strategy.count() == {1: 1}

    @pytest.mark.asyncio()
    async def test_count_after_guild_update_event_for_unknown_guild(self):
        guild_update_event = hikari.GuildUpdateEvent(
            shard=mock.AsyncMock(), old_guild=None, guild=mock.Mock(id=123342123), emojis={}, stickers={}, roles={}
        )
        event_manager = hikari.impl.EventManagerImpl(
            mock.Mock(), mock.Mock(), hikari.Intents.ALL, auto_chunk_members=False
        )
        mock_shards = mock.AsyncMock(shard_count=2, shards={0: mock.Mock(), 1: mock.Mock()})
        strategy = list_status.EventStrategy(event_manager, mock_shards)
        await strategy.open()

        await event_manager.dispatch(guild_update_event)
        guild_update_event.guild.id = hikari.Snowflake(541231)
        await event_manager.dispatch(guild_update_event)

        assert await strategy.count() == {0: 1, 1: 1}

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
        mock_shards = mock.AsyncMock(shard_count=1, shards={0: mock.Mock()})
        strategy = list_status.EventStrategy(event_manager, mock_shards)
        await strategy.open()
        await event_manager.dispatch(ready_event)
        await event_manager.dispatch(guild_available_event)
        await event_manager.dispatch(guild_update_event)
        assert await strategy.count() == {0: 4}

        await event_manager.dispatch(hikari.StartingEvent(app=mock.AsyncMock()))

        assert await strategy.count() == {0: 0}

        await event_manager.dispatch(ready_event)
        await event_manager.dispatch(guild_available_event)
        await event_manager.dispatch(guild_update_event)

        assert await strategy.count() == {0: 4}

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
        mock_shards = mock.AsyncMock(shard_count=2, shards={0: mock.Mock(), 1: mock.Mock()})
        strategy = list_status.EventStrategy(event_manager, mock_shards)
        await strategy.open()
        await event_manager.dispatch(ready_event)
        await event_manager.dispatch(guild_available_event)
        await event_manager.dispatch(guild_update_event)
        assert await strategy.count() == {0: 2, 1: 2}

        await strategy.close()

        assert await strategy.count() == {0: 0, 1: 0}

        await event_manager.dispatch(ready_event)
        await event_manager.dispatch(guild_available_event)
        await event_manager.dispatch(guild_update_event)

        assert await strategy.count() == {0: 0, 1: 0}

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

    def test_from_gateway_bot_when_cacheless(self):
        mock_counter = mock.AsyncMock()
        mock_bot = mock.AsyncMock(_internal.GatewayBotProto, event_manager=mock.Mock())

        manager = list_status.ServiceManager.from_gateway_bot(mock_bot, user_agent="yeet yeet", strategy=mock_counter)

        assert manager.counter is mock_counter
        assert manager.rest is mock_bot.rest
        assert manager.cache is None
        assert manager.shards is mock_bot
        assert manager.user_agent == "yeet yeet"
        mock_bot.event_manager.subscribe.assert_called()

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


@pytest.mark.asyncio()
class TestTopGGService:
    async def test_call_when_count_is_global(self):
        mock_session = mock.Mock()
        mock_session.post.return_value = mock.Mock(__aenter__=mock.AsyncMock(), __aexit__=mock.AsyncMock())
        mock_session.post.return_value.__aenter__.return_value.status = 200
        mock_manager = mock.Mock(get_me=mock.AsyncMock(), user_agent="echo meow")
        mock_manager.counter.count = mock.AsyncMock(return_value=43343)
        mock_manager.get_me.return_value.id = hikari.Snowflake(651231)
        mock_manager.get_session.return_value = mock_session
        mock_manager.shards.shard_count = 64
        service = list_status.TopGGService("meow meow")

        await service(mock_manager)

        mock_session.post.assert_called_once_with(
            "https://top.gg/api/bots/651231/stats",
            headers={"Authorization": "meow meow", "User-Agent": "echo meow"},
            json={"server_count": 43343, "shard_count": 64},
        )

    async def test_call_when_shard_specific(self):
        mock_session = mock.Mock()
        mock_session.post.return_value = mock.Mock(__aenter__=mock.AsyncMock(), __aexit__=mock.AsyncMock())
        mock_session.post.return_value.__aenter__.return_value.status = 200
        mock_session.get.return_value = mock.Mock(__aenter__=mock.AsyncMock(), __aexit__=mock.AsyncMock())
        mock_session.get.return_value.__aenter__.return_value.json.return_value = {
            "shards": [654, 234, 123, 543, 675, 234, 123, 54, 654, 13, 4123, 43, 243]
        }
        mock_session.get.return_value.__aenter__.return_value.status = 200
        mock_session.get.return_value.__aenter__.return_value.raise_for_status = mock.Mock()
        mock_manager = mock.Mock(get_me=mock.AsyncMock(), user_agent="echo meow")
        mock_manager.counter.count = mock.AsyncMock(return_value={5: 34123, 4: 234432, 6: 2399, 3: 54123, 7: 43123})
        mock_manager.get_me.return_value.id = hikari.Snowflake(432123)
        mock_manager.get_session.return_value = mock_session
        mock_manager.shards.shard_count = 16
        service = list_status.TopGGService("meow meow")

        await service(mock_manager)

        mock_session.post.assert_called_once_with(
            "https://top.gg/api/bots/432123/stats",
            headers={"Authorization": "meow meow", "User-Agent": "echo meow"},
            json={
                "shards": [654, 234, 123, 54123, 234432, 34123, 2399, 43123, 654, 13, 4123, 43, 243, 0, 0, 0],
                "shard_count": 16,
            },
        )
        mock_session.post.return_value.__aenter__.assert_awaited_once_with()
        mock_session.post.return_value.__aexit__.assert_awaited_once_with(None, None, None)

    async def test_call_when_count_is_shard_specific_and_shards_not_previously_tracked(self):
        mock_session = mock.Mock()
        mock_session.post.return_value = mock.Mock(__aenter__=mock.AsyncMock(), __aexit__=mock.AsyncMock())
        mock_session.post.return_value.__aenter__.return_value.status = 200
        mock_session.get.return_value = mock.Mock(__aenter__=mock.AsyncMock(), __aexit__=mock.AsyncMock())
        mock_session.get.return_value.__aenter__.return_value.json.return_value = {}
        mock_session.get.return_value.__aenter__.return_value.raise_for_status = mock.Mock()
        mock_session.get.return_value.__aenter__.return_value.status = 200
        mock_manager = mock.Mock(get_me=mock.AsyncMock(), user_agent="aaaaaaaaaaaaaaaaa")
        mock_manager.counter.count = mock.AsyncMock(return_value={5: 34123, 4: 54123, 6: 2399, 3: 234123, 7: 43123})
        mock_manager.get_me.return_value.id = hikari.Snowflake(4326543)
        mock_manager.get_session.return_value = mock_session
        mock_manager.shards.shard_count = 12
        service = list_status.TopGGService("nommy took")

        await service(mock_manager)

        mock_session.get.assert_called_once_with(
            "https://top.gg/api/bots/4326543/stats",
            headers={"Authorization": "nommy took", "User-Agent": "aaaaaaaaaaaaaaaaa"},
        )
        mock_session.get.return_value.__aenter__.assert_awaited_once_with()
        mock_session.get.return_value.__aexit__.assert_awaited_once_with(None, None, None)
        mock_session.post.assert_called_once_with(
            "https://top.gg/api/bots/4326543/stats",
            headers={"Authorization": "nommy took", "User-Agent": "aaaaaaaaaaaaaaaaa"},
            json={"shards": [0, 0, 0, 234123, 54123, 34123, 2399, 43123, 0, 0, 0, 0], "shard_count": 12},
        )
        mock_session.post.return_value.__aenter__.assert_awaited_once_with()
        mock_session.post.return_value.__aexit__.assert_awaited_once_with(None, None, None)

    async def test_call_when_count_is_shard_specific_and_client_shards_not_specified(self):
        mock_session = mock.Mock()
        mock_manager = mock.Mock(get_me=mock.AsyncMock(), shards=None, user_agent="echo meow")
        mock_manager.counter.count = mock.AsyncMock(return_value={0: 231, 1: 343, 2: 32123})
        mock_manager.get_session.return_value = mock_session
        service = list_status.TopGGService("fake token")

        with pytest.raises(RuntimeError, match="Shard count unknown"):
            await service(mock_manager)

        mock_session.post.assert_not_called()


@pytest.mark.asyncio()
class TestBotsGGService:
    async def test_call_when_count_is_global(self):
        mock_session = mock.Mock()
        mock_session.post.return_value = mock.Mock(__aenter__=mock.AsyncMock(), __aexit__=mock.AsyncMock())
        mock_session.post.return_value.__aenter__.return_value.status = 200
        mock_manager = mock.Mock(get_me=mock.AsyncMock(), user_agent="nyaa")
        mock_manager.counter.count = mock.AsyncMock(return_value=876456)
        mock_manager.get_me.return_value.id = hikari.Snowflake(65423)
        mock_manager.get_session.return_value = mock_session
        mock_manager.shards.shard_count = 64
        service = list_status.BotsGGService("pokey")

        await service(mock_manager)

        mock_session.post.assert_called_once_with(
            "https://discord.bots.gg/api/v1/bots/65423/stats",
            headers={"Authorization": "pokey", "User-Agent": "nyaa"},
            json={"guildCount": 876456, "shardCount": 64},
        )
        mock_session.post.return_value.__aenter__.assert_awaited_once_with()
        mock_session.post.return_value.__aexit__.assert_awaited_once_with(None, None, None)

    async def test_call_when_count_is_shard_specific(self):
        mock_session = mock.Mock()
        mock_session.post.return_value = mock.Mock(__aenter__=mock.AsyncMock(), __aexit__=mock.AsyncMock())
        mock_session.post.return_value.__aenter__.return_value.status = 200
        mock_manager = mock.Mock(get_me=mock.AsyncMock(), user_agent="aaaaaaaaaaaaaaaaa")
        mock_manager.counter.count = mock.AsyncMock(return_value={11: 34123, 10: 541234, 7: 54234, 9: 123321})
        mock_manager.get_me.return_value.id = hikari.Snowflake(321321)
        mock_manager.get_session.return_value = mock_session
        mock_manager.shards.shard_count = 32
        service = list_status.BotsGGService("meow")

        await service(mock_manager)

        mock_session.post.assert_called_once_with(
            "https://discord.bots.gg/api/v1/bots/321321/stats",
            headers={"Authorization": "meow", "User-Agent": "aaaaaaaaaaaaaaaaa"},
            json={
                "shards": [
                    {"shardId": 11, "guildCount": 34123},
                    {"shardId": 10, "guildCount": 541234},
                    {"shardId": 7, "guildCount": 54234},
                    {"shardId": 9, "guildCount": 123321},
                ],
                "shardCount": 32,
            },
        )
        mock_session.post.return_value.__aenter__.assert_awaited_once_with()
        mock_session.post.return_value.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.asyncio()
class TestDiscordBotListService:
    async def test_call_when_count_is_global(self):
        mock_session = mock.Mock()
        mock_session.post.return_value = mock.Mock(__aenter__=mock.AsyncMock(), __aexit__=mock.AsyncMock())
        mock_session.post.return_value.__aenter__.return_value.status = 200
        mock_manager = mock.Mock(get_me=mock.AsyncMock(), user_agent="nommy")
        mock_manager.counter.count = mock.AsyncMock(return_value=53345123)
        mock_manager.get_me.return_value.id = hikari.Snowflake(99887766)
        mock_manager.get_session.return_value = mock_session
        mock_manager.shards.shard_count = 128
        service = list_status.DiscordBotListService("sleeping")

        await service(mock_manager)

        mock_session.post.assert_called_once_with(
            "https://discordbotlist.com/api/v1/bots/99887766/stats",
            headers={"Authorization": "sleeping", "User-Agent": "nommy"},
            json={"guilds": 53345123},
        )
        mock_session.post.return_value.__aenter__.assert_awaited_once_with()
        mock_session.post.return_value.__aexit__.assert_awaited_once_with(None, None, None)

    async def test_call_when_count_is_shard_specific(self):
        mock_session = mock.Mock()
        mock_session.post.return_value = mock.Mock(__aenter__=mock.AsyncMock(), __aexit__=mock.AsyncMock())
        mock_session.post.return_value.__aenter__.return_value.status = 200
        mock_session.post.return_value.__aenter__.return_value.raise_for_status = mock.Mock()
        mock_manager = mock.Mock(get_me=mock.AsyncMock(), user_agent="boom")
        mock_manager.counter.count = mock.AsyncMock(return_value={5: 123321, 7: 543345, 9: 12332143, 10: 543123})
        mock_manager.get_me.return_value.id = hikari.Snowflake(234432)
        mock_manager.get_session.return_value = mock_session
        mock_manager.shards.shard_count = 128
        service = list_status.DiscordBotListService("bye")

        await service(mock_manager)

        assert mock_session.post.call_args_list == [
            mock.call(
                "https://discordbotlist.com/api/v1/bots/234432/stats",
                headers={"Authorization": "bye", "User-Agent": "boom"},
                json={"guilds": 123321, "shard_id": 5},
            ),
            mock.call(
                "https://discordbotlist.com/api/v1/bots/234432/stats",
                headers={"Authorization": "bye", "User-Agent": "boom"},
                json={"guilds": 543345, "shard_id": 7},
            ),
            mock.call(
                "https://discordbotlist.com/api/v1/bots/234432/stats",
                headers={"Authorization": "bye", "User-Agent": "boom"},
                json={"guilds": 12332143, "shard_id": 9},
            ),
            mock.call(
                "https://discordbotlist.com/api/v1/bots/234432/stats",
                headers={"Authorization": "bye", "User-Agent": "boom"},
                json={"guilds": 543123, "shard_id": 10},
            ),
        ]
        mock_session.post.return_value.__aenter__.assert_has_awaits(
            [mock.call(), mock.call(), mock.call(), mock.call()]
        )
        mock_session.post.return_value.__aexit__.assert_has_awaits(
            [
                mock.call(None, None, None),
                mock.call(None, None, None),
                mock.call(None, None, None),
                mock.call(None, None, None),
            ]
        )
