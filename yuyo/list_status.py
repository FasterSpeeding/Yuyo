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

__all__: typing.Sequence[str] = [
    "CacheStrategy",
    "CountStrategyProto",
    "EventStrategy",
    "RESTStrategy",
    "InvalidStrategyError",
    "ManagerProto",
    "ServiceProto",
    "ServiceManager",
    "BotsGG",
    "DBoats",
    "TopGG",
]

import asyncio
import datetime
import logging
import time
import typing

import aiohttp
from hikari import config
from hikari import errors as hikari_errors
from hikari import intents
from hikari import snowflakes
from hikari.events import guild_events
from hikari.events import lifetime_events
from hikari.events import shard_events

from . import _utility
from . import backoff

if typing.TYPE_CHECKING:
    from hikari import traits
    from hikari.api import event_manager

    _ServiceManagerT = typing.TypeVar("_ServiceManagerT", bound="ServiceManager")
    _ValueT = typing.TypeVar("_ValueT")

ServiceT = typing.TypeVar("ServiceT", bound="ServiceProto")
StrategyT = typing.TypeVar("StrategyT", bound="CountStrategyProto")
_LOGGER = logging.getLogger("hikari.yuyo")
_strategies: typing.List[typing.Type[CountStrategyProto]] = []
_DEFAULT_USER_AGENT = "Yuyo.last_status instance"
_USER_AGENT = "Yuyo.last_status instance for {}"


def _as_strategy(strategy: typing.Type[StrategyT]) -> typing.Type[StrategyT]:
    _strategies.append(strategy)
    return strategy


class InvalidStrategyError(TypeError):
    """Error raised when a strategy is invalid for the provided manager"""

    __slots__: typing.Sequence[str] = ()


class CountStrategyProto(typing.Protocol):
    __slots__: typing.Sequence[str] = ()

    async def close(self) -> None:
        raise NotImplementedError

    async def open(self) -> None:
        raise NotImplementedError

    async def count(self) -> int:
        raise NotImplementedError

    @classmethod
    def spawn(cls: typing.Type[StrategyT], manager: ManagerProto, /) -> StrategyT:
        raise NotImplementedError


@_as_strategy
class CacheStrategy(CountStrategyProto):
    __slots__: typing.Sequence[str] = ("_cache_service",)

    def __init__(self, cache_service: traits.CacheAware) -> None:
        self._cache_service = cache_service

    async def close(self) -> None:
        return None

    async def open(self) -> None:
        return None

    async def count(self) -> int:
        return len(self._cache_service.cache.get_guilds_view())

    @classmethod
    def spawn(cls, manager: ManagerProto, /) -> CacheStrategy:
        if not manager.cache_service or not manager.shard_service:
            raise InvalidStrategyError

        cache_enabled = manager.cache_service.cache.settings.components & config.CacheComponents.GUILDS
        shard_enabled = manager.shard_service.intents & intents.Intents.GUILDS
        if not cache_enabled or not shard_enabled:
            raise InvalidStrategyError

        return cls(manager.cache_service)


@_as_strategy
class EventStrategy(CountStrategyProto):
    __slots__: typing.Sequence[str] = ("_event_service", "_guild_ids", "_shard_service", "_started")

    def __init__(self, events: traits.EventManagerAware, shards: traits.ShardAware) -> None:
        self._event_service = events
        self._guild_ids: typing.MutableSet[snowflakes.Snowflake] = set()
        self._shard_service = shards
        self._started = False

    async def _on_shard_ready_event(self, event: shard_events.ShardReadyEvent, /) -> None:
        for guild_id in event.unavailable_guilds:
            self._guild_ids.add(guild_id)

    async def _on_starting_event(self, _: lifetime_events.StartingEvent, /) -> None:
        self._guild_ids.clear()

    async def _on_guild_visibility_event(self, event: guild_events.GuildVisibilityEvent, /) -> None:
        if isinstance(event, guild_events.GuildAvailableEvent):
            self._guild_ids.add(event.guild_id)

        elif isinstance(event, guild_events.GuildLeaveEvent):
            self._guild_ids.remove(event.guild_id)

    def _try_unsubscribe(
        self,
        event_type: typing.Type[event_manager.EventT_co],
        callback: event_manager.CallbackT[event_manager.EventT_co],
    ) -> None:
        try:
            self._event_service.event_manager.unsubscribe(event_type, callback)

        except (ValueError, LookupError):
            pass

    async def close(self) -> None:
        if not self._started:
            return

        self._try_unsubscribe(shard_events.ShardReadyEvent, self._on_shard_ready_event)
        self._try_unsubscribe(lifetime_events.StartingEvent, self._on_starting_event)
        self._try_unsubscribe(guild_events.GuildVisibilityEvent, self._on_guild_visibility_event)  # type: ignore[misc]

    async def open(self) -> None:
        if self._started:
            return

        self._event_service.event_manager.subscribe(shard_events.ShardReadyEvent, self._on_shard_ready_event)
        self._event_service.event_manager.subscribe(lifetime_events.StartingEvent, self._on_starting_event)
        self._event_service.event_manager.subscribe(guild_events.GuildVisibilityEvent, self._on_guild_visibility_event)

    async def count(self) -> int:
        return len(self._guild_ids)

    @classmethod
    def spawn(cls, manager: ManagerProto, /) -> EventStrategy:
        events = manager.event_service
        shards = manager.shard_service
        if not events or not shards or not (shards.intents & intents.Intents.GUILDS) == intents.Intents.GUILDS:
            raise InvalidStrategyError

        return cls(events, shards)


# @_as_strategy
class RESTStrategy(CountStrategyProto):
    __slots__: typing.Sequence[str] = ("_count", "_lock", "_requesting", "_time", "_delta")

    def __init__(self, *, delta: datetime.timedelta = datetime.timedelta(hours=1)) -> None:
        self._count = -1
        self._lock: typing.Optional[asyncio.Lock] = None
        self._requesting = False
        self._time = 0.0
        self._delta = delta.total_seconds()

    async def close(self) -> None:
        return None

    async def open(self) -> None:
        return None

    async def count(self) -> int:
        if not self._lock:
            self._lock = asyncio.Lock()

        async with self._lock:
            if self._count == -1:
                self._time = time.perf_counter()
                self._count = await self._calculate_count()

            elif time.perf_counter() - self._time > self._delta and not self._requesting:
                self._time = time.perf_counter()
                asyncio.create_task(self._calculate_count())

            return self._count

    async def _calculate_count(self) -> int:
        if self._requesting:
            raise RuntimeError("Already calculating the count")

        self._requesting = True
        # TODO: logic
        self._requesting = False
        return 42

    @classmethod
    def spawn(cls, manager: ManagerProto, /) -> RESTStrategy:
        raise InvalidStrategyError
        # return cls()


class ManagerProto(typing.Protocol):
    __slots__: typing.Sequence[str] = ()

    @property
    def cache_service(self) -> typing.Optional[traits.CacheAware]:
        raise NotImplementedError

    @property
    def counter(self) -> CountStrategyProto:
        raise NotImplementedError

    @property
    def event_service(self) -> typing.Optional[traits.EventManagerAware]:
        raise NotImplementedError

    @property
    def shard_service(self) -> typing.Optional[traits.ShardAware]:
        raise NotImplementedError

    @property
    def rest_service(self) -> traits.RESTAware:
        raise NotImplementedError

    @property
    def user_agent(self) -> str:
        raise NotImplementedError

    async def get_me(self) -> snowflakes.Snowflake:
        raise NotImplementedError

    async def get_session(self) -> aiohttp.ClientSession:
        raise NotImplementedError


class ServiceProto(typing.Protocol):
    __slot__: typing.Sequence[str] = ()

    async def __call__(self, client: ManagerProto, /) -> None:
        raise NotImplementedError


class _ServiceDescriptor:
    __slots__: typing.Sequence[str] = ("repeat", "function")

    def __init__(self, service: ServiceProto, repeat: float, /) -> None:
        self.function = service
        self.repeat = repeat

    def __repr__(self) -> str:
        return f"_ServiceDescriptor <{self.function}, {self.repeat}>"


class ServiceManager(ManagerProto):
    __slots__: typing.Sequence[str] = (
        "_cache_service",
        "_event_service",
        "_rest_service",
        "services",
        "session",
        "_shard_service",
        "_task",
        "_user_agent",
    )

    def __init__(
        self,
        rest: traits.RESTAware,
        cache: typing.Optional[traits.CacheAware] = None,
        events: typing.Optional[traits.EventManagerAware] = None,
        shards: typing.Optional[traits.ShardAware] = None,
        /,
        *,
        strategy: typing.Optional[CountStrategyProto] = None,
        user_agent: typing.Optional[str] = None,
    ) -> None:
        cache = _utility.try_find_type(traits.CacheAware, cache, rest, events, shards)  # type: ignore[misc]
        events = _utility.try_find_type(traits.EventManagerAware, events, rest, cache, shards)  # type: ignore[misc]
        shards = _utility.try_find_type(traits.ShardAware, shards, rest, cache, events)  # type: ignore[misc]

        self._cache_service = cache
        self._event_service = events
        self._rest_service = rest
        self.services: typing.MutableSequence[_ServiceDescriptor] = []
        self.session: typing.Optional[aiohttp.ClientSession] = None
        self._shard_service = shards
        self._task: typing.Optional[asyncio.Task[None]] = None
        me = cache and cache.cache.get_me()
        self._me: typing.Optional[snowflakes.Snowflake] = me.id if me else None
        self._me_lock: typing.Optional[asyncio.Lock] = None
        self._user_agent = user_agent

        if strategy:
            self._counter = strategy
            return

        for strategy in _strategies:
            try:
                self._counter = strategy.spawn(self)
                break

            except InvalidStrategyError:
                pass

        else:
            raise ValueError("Cannot find a valid guild counting strategy for the provided Hikari client(s)")

    @property
    def cache_service(self) -> typing.Optional[traits.CacheAware]:
        return self._cache_service

    @property
    def counter(self) -> CountStrategyProto:
        return self._counter

    @property
    def event_service(self) -> typing.Optional[traits.EventManagerAware]:
        return self._event_service

    @property
    def rest_service(self) -> traits.RESTAware:
        return self._rest_service

    @property
    def shard_service(self) -> typing.Optional[traits.ShardAware]:
        return self._shard_service

    @property
    def user_agent(self) -> str:
        return self._user_agent or _DEFAULT_USER_AGENT

    def add_service(
        self: _ServiceManagerT, service: ServiceProto, /, repeat: typing.Union[datetime.timedelta, int, float] = 60 * 60
    ) -> _ServiceManagerT:
        if self._task:
            raise RuntimeError("Cannot add a service to an already running manager")

        if isinstance(repeat, datetime.timedelta):
            float_repeat = repeat.total_seconds()

        else:
            float_repeat = float(repeat)

        self._queue_insert(self.services, lambda s: s.repeat > float_repeat, _ServiceDescriptor(service, float_repeat))
        return self

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
            await self._counter.close()

            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def open(self) -> None:
        if not self.services:
            raise RuntimeError("Cannot run a client with no registered services.")

        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        if not self._task:
            await self._counter.open()
            self._task = asyncio.create_task(self._loop())

    async def get_me(self) -> snowflakes.Snowflake:
        if self._me:
            return self._me

        if not self._me_lock:
            self._me_lock = asyncio.Lock()

        async with self._me_lock:
            retry = backoff.Backoff()

            async for _ in retry:
                try:
                    self._me = (await self._rest_service.rest.fetch_my_user()).id
                    break

                except hikari_errors.InternalServerError:
                    continue

                except hikari_errors.RateLimitedError as exc:
                    retry.set_next_backoff(exc.retry_after)

            else:
                self._me = (await self._rest_service.rest.fetch_my_user()).id

        if not self._user_agent:
            self._user_agent = _USER_AGENT.format(self._me)

        return self._me

    async def get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        return self.session

    async def _loop(self) -> None:
        # This acts as a priority queue.
        queue = [(service.repeat, service) for service in self.services]
        while True:
            await asyncio.sleep(sleep := queue[0][0])
            queue = [(time_ - sleep, service) for time_, service in queue]

            while queue[0][0] <= 0:
                service = queue.pop(0)[1]
                time_taken = time.perf_counter()

                try:
                    await service.function(self)

                except Exception as exc:
                    _LOGGER.exception(
                        "Service call to %r service raised an unexpected exception", service.function, exc_info=exc
                    )

                time_taken = time.perf_counter() - time_taken
                queue = [(time_ - time_taken, service) for time_, service in queue]
                self._queue_insert(queue, lambda s: s[0] > service.repeat, (service.repeat, service))

    @staticmethod
    def _queue_insert(
        sequence: typing.MutableSequence[_ValueT], check: typing.Callable[[_ValueT], bool], value: _ValueT
    ) -> None:
        # As we rely on order here for queueing calls we have a dedicated method for inserting based on time left.
        index: int = -1
        for index, sub_value in enumerate(sequence):
            if check(sub_value):
                break

        else:
            index += 1

        sequence.insert(index, value)


async def _log_response(service_name: str, response: aiohttp.ClientResponse, /) -> None:
    if response.status < 300:
        _LOGGER.debug("Posted bot's stats to %s", service_name)
        return

    try:
        content = await response.read()

    except Exception:
        content = b"<Couldn't read response content>"

    if response.status >= 500:
        _LOGGER.warning(
            "Failed to post bot's stats to %s due to internal server error %s: %r",
            service_name,
            response.status,
            content,
        )

    elif response.status == 429:
        _LOGGER.warning("Hit ratelimit while trying to post bot's stats to %s: %r", service_name, content)

    else:
        _LOGGER.exception(
            "Couldn't post bot's stats to %s due to making a malformed request "
            "(%s), is your version of Yuyo up to date? %r",
            service_name,
            response.status,
            content,
        )


class TopGG:
    __slots__: typing.Sequence[str] = ("__token",)

    def __init__(self, token: str, /) -> None:
        self.__token = token

    async def __call__(self, client: ManagerProto, /) -> None:
        me = await client.get_me()
        headers = {"Authorization": self.__token, "User-Agent": client.user_agent}
        json = {"server_count": await client.counter.count()}

        if client.shard_service:
            json["shard_count"] = client.shard_service.shard_count

        session = await client.get_session()

        async with session.post(f"https://top.gg/api/bots/{me}/stats", headers=headers, json=json) as response:
            await _log_response("Top.GG", response)


class BotsGG:
    __slots__: typing.Sequence[str] = ("__token",)

    def __init__(self, token: str, /) -> None:
        self.__token = token

    async def __call__(self, client: ManagerProto, /) -> None:
        me = await client.get_me()
        headers = {"Authorization": self.__token, "User-Agent": client.user_agent}
        json = {"guildCount": await client.counter.count()}

        if client.shard_service:
            json["shardCount"] = client.shard_service.shard_count

        session = await client.get_session()
        async with session.post(
            f"https://discord.bots.gg/api/v1/bots/{me}/stats", headers=headers, json=json
        ) as response:
            await _log_response("Bots.GG", response)


class DBoats:
    __slots__: typing.Sequence[str] = "__token"

    def __init__(self, token: str, /) -> None:
        self.__token = token

    async def __call__(self, client: ManagerProto, /) -> None:
        me = await client.get_me()
        headers = {"Authorization": self.__token, "User-Agent": client.user_agent}
        json = {"server_count": await client.counter.count()}
        session = await client.get_session()

        async with session.post(f"https://discord.boats/api/bots/{me}", headers=headers, json=json) as response:
            await _log_response("Bots.GG", response)
