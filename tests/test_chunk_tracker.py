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

from unittest import mock

import hikari
import pytest

from yuyo import chunk_tracker


class TestChunkRequestFinishedEvent:
    def test_app_property(self):
        mock_app = mock.Mock()

        event = chunk_tracker.ChunkRequestFinishedEvent(mock_app, mock.Mock(), mock.Mock())

        assert event.app is mock_app

    def test_shard_property(self):
        mock_shard = mock.Mock()

        event = chunk_tracker.ChunkRequestFinishedEvent(mock.Mock(), mock_shard, mock.Mock())

        assert event.shard is mock_shard

    def test_chunk_count_property(self):
        mock_data = mock.Mock()

        event = chunk_tracker.ChunkRequestFinishedEvent(mock.Mock(), mock.Mock(), mock_data)

        assert event.chunk_count is mock_data.chunk_count

    def test_first_received_at_property(self):
        mock_data = mock.Mock()

        event = chunk_tracker.ChunkRequestFinishedEvent(mock.Mock(), mock.Mock(), mock_data)

        assert event.first_received_at is mock_data.first_received_at

    def test_guild_id_property(self):
        mock_data = mock.Mock()

        event = chunk_tracker.ChunkRequestFinishedEvent(mock.Mock(), mock.Mock(), mock_data)

        assert event.guild_id is mock_data.guild_id

    def test_last_received_at_property(self):
        mock_data = mock.Mock()

        event = chunk_tracker.ChunkRequestFinishedEvent(mock.Mock(), mock.Mock(), mock_data)

        assert event.last_received_at is mock_data.last_received_at

    def test_missed_chunks_at_property(self):
        mock_data = mock.Mock()

        event = chunk_tracker.ChunkRequestFinishedEvent(mock.Mock(), mock.Mock(), mock_data)

        assert event.missed_chunks is mock_data.missing_chunks

    def test_not_found_ids_at_property(self):
        mock_data = mock.Mock()

        event = chunk_tracker.ChunkRequestFinishedEvent(mock.Mock(), mock.Mock(), mock_data)

        assert event.not_found_ids is mock_data.not_found_ids


class TestFinishedChunkingEvent:
    def test_app_property(self):
        mock_app = mock.Mock()

        event = chunk_tracker.FinishedChunkingEvent(mock_app)

        assert event.app is mock_app


class TestShardFinishedChunkingEvent:
    def test_app_property(self):
        mock_app = mock.Mock()

        event = chunk_tracker.ShardFinishedChunkingEvent(mock_app, mock.Mock())

        assert event.app is mock_app

    def test_shard_property(self):
        mock_shard = mock.Mock()

        event = chunk_tracker.ShardFinishedChunkingEvent(mock.Mock(), mock_shard)

        assert event.shard is mock_shard

    def test_incomplete_guild_ids_property(self):
        event = chunk_tracker.ShardFinishedChunkingEvent(
            mock.Mock(),
            mock.Mock(),
            incomplete_guild_ids=(hikari.Snowflake(123), hikari.Snowflake(54), hikari.Snowflake(654)),
        )

        assert event.incomplete_guild_ids == (123, 54, 654)

    def test_missed_guild_ids_property(self):
        event = chunk_tracker.ShardFinishedChunkingEvent(
            mock.Mock(), mock.Mock(), missed_guild_ids=(hikari.Snowflake(123312), hikari.Snowflake(433))
        )

        assert event.missed_guild_ids == (123312, 433)


class TestChunkTracker:
    def test_from_gateway_bot(self):
        mock_bot = mock.Mock()

        tracker = chunk_tracker.ChunkTracker.from_gateway_bot(mock_bot)

        assert tracker._event_manager is mock_bot.event_manager
        assert tracker._rest is mock_bot
        assert tracker._shards is mock_bot

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_request_guild_members(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_set_auto_chunk_members(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test(self):
        ...
