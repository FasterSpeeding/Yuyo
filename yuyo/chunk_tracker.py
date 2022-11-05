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
"""Utility class for tracking request guild member responses."""
from __future__ import annotations

__all__: list[str] = []

import base64
import datetime
import random
import typing

import hikari

if typing.TYPE_CHECKING:
    from typing_extensions import Self


class _RequestData:
    __slots__ = ("chunk_count", "first_received_at", "guild_id", "is_startup", "last_received_at", "missing_chunks")

    def __init__(
        self,
        guild_id: hikari.Snowflake,
        /,
        *,
        chunk_count: typing.Optional[int] = None,
        first_received_at: typing.Optional[datetime.datetime] = None,
        is_startup: bool = False,
        last_received_at: typing.Optional[datetime.datetime] = None,
        missing_chunks: typing.Optional[typing.Set[int]] = None,
    ) -> None:
        self.chunk_count: typing.Optional[int] = chunk_count
        self.first_received_at: typing.Optional[datetime.datetime] = first_received_at
        self.guild_id: hikari.Snowflake = guild_id
        self.is_startup: bool = is_startup
        self.last_received_at: typing.Optional[datetime.datetime] = last_received_at
        self.missing_chunks: typing.Optional[typing.Set[int]] = missing_chunks


class ChunkRequestFinished(hikari.Event):
    """Event that's dispatched when a specific chunk request has finished."""

    __slots__ = ("_app", "_data", "_shard")

    def __init__(self, app: hikari.RESTAware, shard: hikari.api.GatewayShard, data: _RequestData, /) -> None:
        """Initialise a chunk request finished event.

        This should never be initialised directly.
        """
        self._app = app
        self._data = data
        self._shard = shard

    @property
    def app(self) -> hikari.RESTAware:
        # <<inherited docstring from hikari.events.base_events.Event>>.
        return self._app

    @property
    def shard(self) -> hikari.api.GatewayShard:
        # <<inherited docstring from hikari.events.shard_events.ShardEvent>>.
        return self._shard

    @property
    def chunk_count(self) -> int:
        """The amount of chunk events which should've been received for this request."""
        assert self._data.chunk_count
        return self._data.chunk_count

    @property
    def first_received_at(self) -> datetime.datetime:
        """When the first response was received."""
        assert self._data.first_received_at
        return self._data.first_received_at

    @property
    def guild_id(self) -> hikari.Snowflake:
        """Id of the guild this chunk request was for."""
        return self._data.guild_id

    @property
    def last_received_at(self) -> datetime.datetime:
        """When the last response was received."""
        assert self._data.last_received_at
        return self._data.last_received_at

    @property
    def missed_chunks(self) -> typing.Collection[int]:
        """Collection of the chunk responses which were missed (if any)."""
        return self._data.missing_chunks or ()


class ChunkingFinishedEvent(hikari.Event):
    """Event that's dispatched when the startup chunking has finished for the bot.

    This indicates that any cache member and presences resources should be
    complete globally.
    """

    __slots__ = ()

    def __init__(self, app: hikari.RESTAware, /) -> None:
        """Initialise a chunking finished event.

        This should never be initialised directly.
        """
        self._app = app

    @property
    def app(self) -> hikari.RESTAware:
        # <<inherited docstring from hikari.events.base_events.Event>>.
        return self._app


class ShardChunkingFinishedEvent(hikari.ShardEvent):
    """Event that's dispatched when the startup chunking has finished for a shard.

    This indicates that any cache member and presences resources should be
    complete for guilds covered by this shard.
    """

    __slots__ = ("_app", "_shard")

    def __init__(
        self,
        app: hikari.RESTAware,
        shard: hikari.api.GatewayShard,
        /,
        *,
        incomplete_guild_ids: typing.Sequence[hikari.Snowflake] = (),
        missing_guild_ids: typing.Sequence[hikari.Snowflake] = (),
    ) -> None:
        """Initialise a shard chunking finished event.

        This should never be initialised directly.
        """
        self._app = app
        self._incomplete_guild_ids = incomplete_guild_ids
        self._missing_guild_ids = missing_guild_ids
        self._shard = shard

    @property
    def app(self) -> hikari.RESTAware:
        # <<inherited docstring from hikari.events.base_events.Event>>.
        return self._app

    @property
    def shard(self) -> hikari.api.GatewayShard:
        # <<inherited docstring from hikari.events.shard_events.ShardEvent>>.
        return self._shard

    @property
    def incomplete_guild_ids(self) -> typing.Sequence[hikari.Snowflake]:
        """Sequence of the IDs of guilds some chunk responses were missed for."""
        return self._incomplete_guild_ids

    @property
    def missed_guild_ids(self) -> typing.Sequence[hikari.Snowflake]:
        """Sequence of the IDs of guilds no chunk responses were received for."""
        return self._missing_guild_ids


class ChunkTracker:
    """Chunk payload event tracker.

    This will dispatch [ShardChunkingFinishedEvent][], [ChunkingFinishedEvent][]
    and [ChunkRequestFinished][] events.
    """

    __slots__ = (
        "_auto_chunk_members",
        "_chunk_presences",
        "_event_manager",
        "_identify_guild_ids",
        "_requests",
        "_shards",
    )

    def __init__(
        self,
        event_manager: hikari.api.EventManager,
        shards: hikari.ShardAware,
        /,  # *, track_unknowns: bool = True
    ) -> None:
        """Initialise a chunk tracker.

        For a shorthand for initialising this from a [hikari.traits.GatewayBotAware][]
        see [ChunkTracker.from_gateway_bot][].

        Parameters
        ----------
        event_manager
            The event manager this chunk tracker should dispatch events over.
        shards
            The shard aware object this should use.
        """
        self._auto_chunk_members = False
        self._chunk_presences = False
        self._event_manager = event_manager
        self._identify_guild_ids: typing.Dict[int, typing.Set[hikari.Snowflake]] = {}
        self._requests: typing.Dict[str, _RequestData] = {}
        self._shards = shards

    @classmethod
    def from_gateway_bot(cls, bot: hikari.GatewayBotAware, /) -> Self:
        """Initialise a chunk tracker from a gateway bot.

        Parameters
        ----------
        bot
            The gateway bot this chunk tracker should use.
        """
        return cls(bot.event_manager, bot)

    async def request_guild_members(
        self,
        guild: hikari.SnowflakeishOr[hikari.PartialGuild],
        *,
        include_presences: hikari.UndefinedOr[bool] = hikari.UNDEFINED,
        query: str = "",
        limit: int = 0,
        users: hikari.UndefinedOr[hikari.SnowflakeishSequence[hikari.User]] = hikari.UNDEFINED,
    ) -> None:
        """Request for a guild chunk.

        !!! note
            To request the full list of members, leave `query` as `""` (empty
            string) and `limit` as `0`.

        Parameters
        ----------
        guild
            The guild to request chunk for.
        include_presences
            If provided, whether to request presences.
        query
            If not `""`, request the members who's usernames starts with the string.
        limit
            Maximum number of members to send matching the query.
        users
            If provided, the users to request for.

        Raises
        ------
        ValueError
            When trying to specify `users` with `query`/`limit`, if `limit` is not between
            0 and 100, both inclusive or if `users` length is over 100.
        hikari.errors.MissingIntentError
            When trying to request presences without the `GUILD_MEMBERS` or when trying to
            request the full list of members without `GUILD_PRESENCES`.
        """
        nonce = base64.b64encode(random.getrandbits(128).to_bytes(16, "big")).rstrip(b"=").decode()
        await self._shards.request_guild_members(
            guild, include_presences=include_presences, query=query, limit=limit, users=users, nonce=nonce
        )

    def set_auto_chunk_members(self, state: bool, /, *, chunk_presences: bool = True) -> Self:
        """Configure whether this should request member chunks in response to GUILD_CREATE.

        !!! warning
            This will be ignored if [Intents.GUILD_MEMBERS][hikari.intents.Intents.GUILD_MEMBERS]
            hasn't been declared.

        Parameters
        ----------
        state
            Whether this should request member chunks when GUILD_CREATE events are received.
        chunk_presences
            Whether this should also request member presences on these member chunks.

            This will be ignored if [Intents.GUILD_PRESENCES][hikari.intents.Intents.GUILD_PRESENCES]
            hasn't been declared.

        Returns
        -------
        Self
            The chunk tracker object to enable call chaining.
        """
        if state:
            self._auto_chunk_members = state
            self._chunk_presences = chunk_presences

        else:
            self._chunk_presences = False

        return self

    async def _dispatch_finished(self, event: hikari.ShardPayloadEvent, data: _RequestData, /) -> None:
        await self._event_manager.dispatch(ChunkRequestFinished(event.app, event.shard, data))
        if not data.is_startup:
            return

        try:
            self._identify_guild_ids[event.shard.id].remove(data.guild_id)
        except KeyError:
            pass

        if self._identify_guild_ids[event.shard.id]:
            return

        del self._identify_guild_ids[event.shard.id]
        await self._event_manager.dispatch(ShardChunkingFinishedEvent(event.app, event.shard))
        if not self._identify_guild_ids:
            await self._event_manager.dispatch(ChunkingFinishedEvent(event.app))

    async def _on_payload_event(self, event: hikari.ShardPayloadEvent, /) -> None:
        if (
            event.name == "GUILD_CREATE"
            and self._auto_chunk_members
            and event.payload.get("large")
            and event.shard.intents & hikari.Intents.GUILD_MEMBERS
        ):
            guild_id = hikari.Snowflake(event.payload["id"])
            _RequestData(guild_id, is_startup=True)
            await self.request_guild_members(
                guild_id,
                include_presences=self._chunk_presences and bool(event.shard.intents & hikari.Intents.GUILD_PRESENCES),
            )

        if event.name != "GUILD_MEMBERS_CHUNK":
            return

        nonce = event.payload.get("nonce")
        if not nonce:
            return

        chunk_count = int(event.payload["chunk_count"])
        chunk_index = int(event.payload["chunk_index"])
        date = datetime.datetime.now(tz=datetime.timezone.utc)
        guild_id = hikari.Snowflake(event.payload["guild_id"])
        nonce = str(nonce)

        data = self._requests.get(nonce)
        if data:
            if data.missing_chunks is None:
                data.chunk_count = chunk_count
                data.first_received_at = date
                data.missing_chunks = set(range(chunk_count))

            data.last_received_at = date
            data.missing_chunks.remove(chunk_index)

            if not data.missing_chunks:
                del self._requests[nonce]
                await self._dispatch_finished(event, data)

            return

        chunks = set(range(chunk_count))
        chunks.remove(chunk_index)
        data = _RequestData(
            guild_id, chunk_count=chunk_count, first_received_at=date, last_received_at=date, missing_chunks=chunks
        )
        if data.missing_chunks:
            self._requests[nonce] = data

        else:
            await self._dispatch_finished(event, data)
