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

__all__: typing.Sequence[str] = [
    "ChunkRequestFinished",
    "ChunkTracker",
    "ChunkingFinishedEvent",
    "ShardChunkingFinishedEvent",
]

import asyncio
import base64
import datetime
import functools
import logging
import random
import typing

import hikari

if typing.TYPE_CHECKING:
    import typing_extensions
    from typing_extensions import Self

    _P = typing_extensions.ParamSpec("_P")
    _T = typing.TypeVar("_T")
    _CoroT = typing.Coroutine[typing.Any, typing.Any, _T]


_LOGGER = logging.getLogger("hikari.yuyo.chunk_trackers")


class ChunkRequestFinished(hikari.Event):
    """Event that's dispatched when a specific chunk request has finished.

    This will be fired for every chunk request which has a nonce.
    """

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
        return self._data.first_received_at

    @property
    def guild_id(self) -> hikari.Snowflake:
        """Id of the guild this chunk request was for."""
        return self._data.guild_id

    @property
    def last_received_at(self) -> datetime.datetime:
        """When the last response was received."""
        return self._data.last_received_at

    @property
    def missed_chunks(self) -> typing.Collection[int]:
        """Collection of the chunk responses which were missed (if any)."""
        return self._data.missing_chunks or ()

    @property
    def not_found_ids(self) -> typing.Collection[hikari.Snowflake]:
        """Collection of the User IDs which weren't found.

        This is only relevant when `users` was specified while requesting the members.
        """
        return self._data.not_found_ids


class ChunkingFinishedEvent(hikari.Event):
    """Event that's dispatched when the startup chunking has finished for the bot.

    This indicates that any cache member and presences resources should be
    complete globally.

    This will only be fired after bot startups.
    """

    __slots__ = ("_app",)

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

    This will be fired after every shard identify which triggers chunking
    (including re-identifies).
    """

    __slots__ = ("_app", "_incomplete_guild_ids", "_missing_guild_ids", "_shard")

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


def _log_task_exc(
    message: str, /
) -> typing.Callable[[typing.Callable[_P, typing.Awaitable[_T]]], typing.Callable[_P, _CoroT[_T]]]:
    """Log the exception when a task raises instead of leaving it up to the gods."""

    def decorator(callback: typing.Callable[_P, typing.Awaitable[_T]], /) -> typing.Callable[_P, _CoroT[_T]]:
        @functools.wraps(callback)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            try:
                return await callback(*args, **kwargs)

            except Exception as exc:
                _LOGGER.exception(message, exc_info=exc)
                raise exc from None  # noqa: R101  # use bare raise in except handler?

        return wrapper

    return decorator


class _RequestData:
    __slots__ = (
        "chunk_count",
        "first_received_at",
        "guild_id",
        "last_received_at",
        "missing_chunks",
        "not_found_ids",
        "shard",
    )

    def __init__(
        self,
        shard: hikari.api.GatewayShard,
        guild_id: hikari.Snowflake,
        /,
        *,
        chunk_count: typing.Optional[int] = None,
        first_received_at: datetime.datetime,
        last_received_at: datetime.datetime,
        missing_chunks: typing.Optional[typing.Set[int]] = None,
        not_found_ids: typing.Optional[typing.Set[hikari.Snowflake]] = None,
    ) -> None:
        self.chunk_count: typing.Optional[int] = chunk_count
        self.first_received_at: datetime.datetime = first_received_at
        self.guild_id: hikari.Snowflake = guild_id
        self.last_received_at: datetime.datetime = last_received_at
        self.missing_chunks: typing.Optional[typing.Set[int]] = missing_chunks
        self.not_found_ids: typing.Set[hikari.Snowflake] = not_found_ids or set()
        self.shard: hikari.api.GatewayShard = shard


def _now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


_TIMEOUT = datetime.timedelta(seconds=5)


class _ShardInfo:
    __slots__ = ("guild_ids", "last_received_at", "shard")

    def __init__(self, shard: hikari.api.GatewayShard, guild_ids: typing.Sequence[hikari.Snowflake], /) -> None:
        self.guild_ids = set(guild_ids)
        self.last_received_at = _now()
        self.shard = shard


class _TimedOutShard:
    __slots__ = ("incomplete_guild_ids", "shard_info")

    def __init__(self, shard_info: _ShardInfo) -> None:
        self.incomplete_guild_ids: typing.List[hikari.Snowflake] = []
        self.shard_info: _ShardInfo = shard_info

    def mark_incomplete(self, guild_id: hikari.Snowflake, /) -> None:
        try:
            self.shard_info.guild_ids.remove(guild_id)

        except KeyError:
            pass

        else:
            self.incomplete_guild_ids.append(guild_id)

    def missing_guild_ids(self) -> typing.Sequence[hikari.Snowflake]:
        return list(self.shard_info.guild_ids.difference(self.incomplete_guild_ids))


class ChunkTracker:
    """Chunk payload event tracker.

    This will dispatch [ShardChunkingFinishedEvent][yuyo.chunk_tracker.ShardChunkingFinishedEvent],
    [ChunkingFinishedEvent][yuyo.chunk_tracker.ChunkingFinishedEvent]
    and [ChunkRequestFinished][yuyo.chunk_tracker.ChunkRequestFinished] events.
    """

    __slots__ = (
        "_auto_chunk_members",
        "_chunk_presences",
        "_event_manager",
        "_requests",
        "_rest",
        "_shards",
        "_task",
        "_tracked_identifies",
    )

    def __init__(
        self,
        event_manager: hikari.api.EventManager,
        rest: hikari.RESTAware,
        shards: hikari.ShardAware,
        /,
    ) -> None:
        """Initialise a chunk tracker.

        For a shorthand for initialising this from a [hikari.traits.GatewayBotAware][]
        see [ChunkTracker.from_gateway_bot][yuyo.chunk_tracker.ChunkTracker.from_gateway_bot].

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
        self._requests: typing.Dict[str, _RequestData] = {}
        self._rest = rest
        self._shards = shards
        self._task: typing.Optional[asyncio.Task[None]] = None
        self._tracked_identifies: typing.Dict[int, _ShardInfo] = {}
        event_manager.subscribe(hikari.ShardPayloadEvent, self._on_payload_event)
        event_manager.subscribe(hikari.ShardReadyEvent, self._on_shard_ready_event)

    @classmethod
    def from_gateway_bot(cls, bot: hikari.GatewayBotAware, /) -> Self:
        """Initialise a chunk tracker from a gateway bot.

        Parameters
        ----------
        bot
            The gateway bot this chunk tracker should use.
        """
        return cls(bot.event_manager, bot, bot)

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

    def _ensure_loop(self) -> None:
        if not self._task:
            self._task = asyncio.get_running_loop().create_task(self._loop())
            self._task.add_done_callback(self._unset_task)

    def _unset_task(self, task: asyncio.Task[None], /) -> None:
        self._task = None

    @_log_task_exc("Chunk tracker crashed")
    async def _loop(self) -> None:
        timed_out_requests: typing.List[_RequestData] = []
        timed_out_shards: typing.Dict[int, _TimedOutShard] = {}

        while self._tracked_identifies or self._requests:
            await asyncio.sleep(1)
            date = _now()
            for shard_info in self._tracked_identifies.copy().values():
                if date - shard_info.last_received_at < _TIMEOUT:
                    continue

                timed_out_shards[shard_info.shard.id] = _TimedOutShard(shard_info)
                del self._tracked_identifies[shard_info.shard.id]

            for nonce, request_info in self._requests.items():
                if shard_info := timed_out_shards.get(request_info.shard.id):
                    shard_info.mark_incomplete(request_info.guild_id)

                if date - request_info.last_received_at < _TIMEOUT:
                    continue

                timed_out_requests.append(request_info)
                del self._requests[nonce]

            await asyncio.gather(*map(self._dispatch_finished, timed_out_requests))
            await asyncio.gather(
                *(
                    self._dispatch_shard_finished(
                        info.shard_info.shard,
                        incomplete_guild_ids=info.incomplete_guild_ids,
                        missing_guild_ids=info.missing_guild_ids(),
                    )
                    for info in timed_out_shards.values()
                )
            )
            timed_out_requests.clear()
            timed_out_shards.clear()

    async def _dispatch_finished(self, data: _RequestData, /) -> None:
        await self._event_manager.dispatch(ChunkRequestFinished(self._rest, data.shard, data))
        try:
            shard_info = self._tracked_identifies[data.shard.id]
            shard_info.guild_ids.remove(data.guild_id)
        except KeyError:
            return

        if shard_info.guild_ids:
            shard_info.last_received_at = _now()
            return

        del self._tracked_identifies[data.shard.id]
        await self._dispatch_shard_finished(shard_info.shard)

    async def _dispatch_shard_finished(
        self,
        shard: hikari.api.GatewayShard,
        /,
        *,
        incomplete_guild_ids: typing.Sequence[hikari.Snowflake] = (),
        missing_guild_ids: typing.Sequence[hikari.Snowflake] = (),
    ) -> None:
        event = ShardChunkingFinishedEvent(
            self._rest, shard, incomplete_guild_ids=incomplete_guild_ids, missing_guild_ids=missing_guild_ids
        )
        await self._event_manager.dispatch(event)
        if not self._tracked_identifies:
            await self._event_manager.dispatch(ChunkingFinishedEvent(self._rest))

    async def _on_shard_ready_event(self, event: hikari.events.ShardReadyEvent, /) -> None:
        self._tracked_identifies[event.shard.id] = _ShardInfo(event.shard, event.unavailable_guilds)

    async def _on_payload_event(self, event: hikari.ShardPayloadEvent, /) -> None:
        if event.name == "GUILD_CREATE":
            guild_id = hikari.Snowflake(event.payload["id"])

            if (
                self._auto_chunk_members
                and event.payload.get("large")
                and event.shard.intents & hikari.Intents.GUILD_MEMBERS
            ):
                include_presences = self._chunk_presences and bool(event.shard.intents & hikari.Intents.GUILD_PRESENCES)
                await self.request_guild_members(guild_id, include_presences=include_presences)
                return

            try:
                shard_info = self._tracked_identifies[event.shard.id]
                shard_info.guild_ids.remove(guild_id)

            except KeyError:
                pass

            else:
                if not shard_info.guild_ids:
                    await self._dispatch_shard_finished(event.shard)

        if event.name != "GUILD_MEMBERS_CHUNK":
            return

        nonce = event.payload.get("nonce")
        if not nonce:
            return

        chunk_count = int(event.payload["chunk_count"])
        chunk_index = int(event.payload["chunk_index"])
        date = _now()
        guild_id = hikari.Snowflake(event.payload["guild_id"])
        nonce = str(nonce)
        not_found_ids = event.payload.get("not_found")

        data = self._requests.get(nonce)
        if data:
            if data.missing_chunks is None:
                data.chunk_count = chunk_count
                data.first_received_at = date
                data.missing_chunks = set(range(chunk_count))

            data.last_received_at = date
            data.missing_chunks.remove(chunk_index)

            if not_found_ids:
                data.not_found_ids.update(map(hikari.Snowflake, not_found_ids))

            if not data.missing_chunks:
                del self._requests[nonce]
                await self._dispatch_finished(data)

            else:
                self._ensure_loop()

            return

        chunks = set(range(chunk_count))
        chunks.remove(chunk_index)
        not_found_ids = {hikari.Snowflake(value) for value in not_found_ids or ()}
        data = _RequestData(
            event.shard,
            guild_id,
            chunk_count=chunk_count,
            first_received_at=date,
            last_received_at=date,
            missing_chunks=chunks,
            not_found_ids=not_found_ids,
        )
        if data.missing_chunks:
            self._requests[nonce] = data
            self._ensure_loop()

        else:
            await self._dispatch_finished(data)
