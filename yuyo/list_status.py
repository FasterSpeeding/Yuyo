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

__all__: typing.Sequence[str] = ["Service", "ServiceManager"]

import asyncio
import datetime
import typing

import aiohttp

if typing.TYPE_CHECKING:
    from hikari import traits

ServiceT = typing.TypeVar("ServiceT", bound="Service")
ValueT = typing.TypeVar("ValueT")


class Service(typing.Protocol):
    __slot__: typing.Sequence[str] = ()

    async def __call__(
        self,
        client: aiohttp.ClientSession,
        /,
        cache: typing.Optional[traits.CacheAware],
        rest: traits.RESTAware,
        shards: traits.ShardAware,
    ) -> None:
        raise NotImplementedError


class _ServiceDescriptor:
    __slots__: typing.Sequence[str] = ("repeat", "function")

    def __init__(self, service: Service, repeat: float, /) -> None:
        self.function = service
        self.repeat = repeat

    def __repr__(self) -> str:
        return f"_ServiceDescriptor <{self.function}, {self.repeat}>"


class ServiceManager:
    __slots__: typing.Sequence[str] = ("cache_service", "rest_service", "services", "session", "shard_service", "_task")

    def __init__(
        self,
        rest: traits.RESTAware,
        shards: typing.Optional[traits.ShardAware] = None,
        cache: typing.Optional[traits.CacheAware] = None,
        /,
    ) -> None:
        if shards is not None:
            pass

        elif isinstance(rest, traits.ShardAware):
            shards = rest

        elif isinstance(cache, traits.ShardAware):
            shards = cache

        else:
            raise ValueError("Missing shard aware Hikari implementation")

        if cache is not None:
            pass

        elif isinstance(rest, traits.CacheAware):
            cache = rest

        elif isinstance(shards, traits.CacheAware):  # type: ignore[unreachable]
            cache = shards

        # TODO: log/warn if this is running cache-lessly
        # TODO: can i make a function for this boilerplate of if elif statements?

        self.cache_service = cache
        self.rest_service = rest
        self.services: typing.MutableSequence[_ServiceDescriptor] = []
        self.session: typing.Optional[aiohttp.ClientSession] = None
        self.shard_service = shards
        self._task: typing.Optional[asyncio.Task[None]] = None

    def add_service(self, service: Service, /, repeat: typing.Union[datetime.timedelta, int, float]) -> None:
        if self._task:
            raise RuntimeError("Cannot add a service to an already running manager")

        if isinstance(repeat, datetime.timedelta):
            float_repeat = repeat.total_seconds()

        else:
            float_repeat = float(repeat)

        self._queue_insert(self.services, lambda s: s.repeat > float_repeat, _ServiceDescriptor(service, float_repeat))

    def with_service(
        self, repeat: typing.Union[datetime.timedelta, int, float], /
    ) -> typing.Callable[[ServiceT], ServiceT]:
        def decorator(service: ServiceT, /) -> ServiceT:
            self.add_service(service, repeat=repeat)
            return service

        return decorator

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def open(self) -> None:
        if not self.services:
            raise RuntimeError("Cannot run a client with no registered services.")

        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        if not self._task:
            self._task = asyncio.create_task(self._loop())

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        return self.session

    async def _loop(self) -> None:
        # This acts as a priority queue.
        queue = [(service.repeat, service) for service in self.services]
        while True:
            await asyncio.sleep(sleep := queue[0][0])
            queue = [(time - sleep, service) for time, service in queue]

            while queue[0][0] <= 0:
                session = await self._get_session()
                service = queue.pop(0)[1]
                # TODO: catch any error and warn or log based on it here
                await service.function(session, self.cache_service, self.rest_service, self.shard_service)
                self._queue_insert(queue, lambda s: s[0] > service.repeat, (service.repeat, service))

    @staticmethod
    def _queue_insert(
        sequence: typing.MutableSequence[ValueT], check: typing.Callable[[ValueT], bool], value: ValueT
    ) -> None:
        # As we rely on order here for queueing calls we have a dedicated method for inserting based on time left.
        index: int = -1
        for index, sub_value in enumerate(sequence):
            if check(sub_value):
                break

        else:
            index += 1

        sequence.insert(index, value)
