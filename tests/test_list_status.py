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

    @pytest.mark.asyncio()
    async def test_count_when_iter_raises_closed_client(self):
        ...


class TestEventStrategy:
    ...


class TestServiceManager:
    ...


class TestTopGGService:
    ...


class TestBotsGGService:
    ...


class TestDiscordBotListService:
    ...
