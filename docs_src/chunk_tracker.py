# -*- coding: utf-8 -*-
# Yuyo Examples - A collection of examples for Yuyo.
# Written in 2023 by Faster Speeding Lucina@lmbyrne.dev
#
# To the extent possible under law, the author(s) have dedicated all copyright
# and related and neighboring rights to this software to the public domain worldwide.
# This software is distributed without any warranty.
#
# You should have received a copy of the CC0 Public Domain Dedication along with this software.
# If not, see <https://creativecommons.org/publicdomain/zero/1.0/>.

# pyright: reportUnusedFunction=none
import collections.abc  # pyright: ignore[reportUnusedImport]
import datetime  # pyright: ignore[reportUnusedImport]

import hikari

import yuyo


def create_client(bot: hikari.GatewayBotAware):
    yuyo.chunk_tracker.ChunkTracker.from_gateway_bot(bot)


def chunk_request_finished_event(bot: hikari.impl.GatewayBot):
    @bot.listen()
    async def on_chunk_request_finished(event: yuyo.chunk_tracker.ChunkRequestFinishedEvent) -> None:
        event.app
        event.shard  # type: hikari.api.GatewayShard
        event.chunk_count  # type: int
        event.first_received_at  # type: datetime.datetime
        event.guild_id  # type: hikari.Snowflake
        event.last_received_at  # type: datetime.datetime
        event.missed_chunks  # type: collections.abc.Collection[int]
        event.not_found_ids  # type: collections.abc.Collection[hikari.Snowflake]


def finished_chunking_event(bot: hikari.impl.GatewayBot):
    @bot.listen()
    async def on_finished_chunking(event: yuyo.chunk_tracker.FinishedChunkingEvent) -> None:
        event.app


def shard_finished_chunking_event(bot: hikari.impl.GatewayBot):
    @bot.listen()
    async def on_shard_finished_chunking(event: yuyo.chunk_tracker.ShardFinishedChunkingEvent) -> None:
        event.app
        event.shard  # type: hikari.api.GatewayShard
        event.incomplete_guild_ids  # collections.abc.Sequence[hikari.Snowflake]
        event.missed_guild_ids  # collections.abc.Sequence[hikari.Snowflake]
