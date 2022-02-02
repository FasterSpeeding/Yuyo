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

import copy
import datetime
import typing
from collections import abc as collections

import hikari


class _RequestData:
    __slots__ = ("chunk_count", "first_received_at", "guild_id", "last_received_at", "missing_chunks")

    def __init__(
        self,
        *,
        chunk_count: int = -1,
        first_received_at: typing.Optional[datetime.datetime] = None,
        guild_id: typing.Optional[hikari.Snowflake] = None,
        last_received_at: typing.Optional[datetime.datetime] = None,
        missing_chunks: typing.Optional[typing.Set[int]] = None,
    ) -> None:
        self.chunk_count = chunk_count
        self.first_received_at = first_received_at
        self.guild_id = guild_id
        self.last_received_at = last_received_at
        self.missing_chunks = missing_chunks


class RequestInfo:
    __slots__ = ("_data",)

    def __init__(self, data: _RequestData, /) -> None:
        self._data = copy.copy(data)
        self._data.missing_chunks = data.missing_chunks.copy() if data.missing_chunks is not None else None

    @property
    def first_received_at(self) -> typing.Optional[datetime.datetime]:
        return self._data.first_received_at

    @property
    def last_received_at(self) -> typing.Optional[datetime.datetime]:
        return self._data.last_received_at

    @property
    def has_finished(self) -> bool:
        return self._data.chunk_count != -1 and not self._data.missing_chunks

    @property
    def has_started(self) -> bool:
        return self._data.missing_chunks is not None

    @property
    def missing_chunks(self) -> collections.Collection[int]:
        return self._data.missing_chunks or set()


class ChunkTracker:
    __slots__ = ("_guild_nonces", "_history_limit", "_requests")

    def __init__(self, *, history_limit: int = 1000, track_unknowns: bool = False) -> None:
        self._guild_nonces: dict[hikari.Snowflake, set[str]] = {}
        self._history_limit = int(history_limit)
        self._requests: dict[str, _RequestData] = {}

        if self._history_limit < 1:
            raise ValueError("history_limit must be greater than 0")

    async def _on_payload_event(self, event: hikari.ShardPayloadEvent, /) -> None:
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
                data.guild_id = guild_id
                data.missing_chunks = set(range(chunk_count))

                try:
                    self._guild_nonces[guild_id].add(nonce)

                except KeyError:
                    self._guild_nonces[guild_id] = {nonce}

            data.last_received_at = date
            data.missing_chunks.remove(chunk_index)
            return

        chunks = set(range(chunk_count))
        chunks.remove(chunk_index)
        self._requests[nonce] = _RequestData(
            chunk_count=chunk_count,
            first_received_at=date,
            guild_id=guild_id,
            last_received_at=date,
            missing_chunks=chunks,
        )

        if len(self._requests) > self._history_limit:
            key, value = next(iter(self._requests.items()))
            del self._requests[key]
            if value.guild_id is not None:
                nonces = self._guild_nonces[value.guild_id]
                nonces.remove(key)
                if not nonces:
                    del self._guild_nonces[value.guild_id]

    def get_guild_requests(
        self, guild: hikari.SnowflakeishOr[hikari.PartialGuild], /
    ) -> collections.Sequence[RequestInfo]:
        if request_ids := self._guild_nonces.get(hikari.Snowflake(guild)):
            return [RequestInfo(self._requests[nonce]) for nonce in request_ids]

        return []

    def get_request(self, chunk_id: str, /) -> typing.Optional[RequestInfo]:
        if data := self._requests.get(chunk_id):
            return RequestInfo(data)
