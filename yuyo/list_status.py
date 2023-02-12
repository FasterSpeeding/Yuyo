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
"""Utility classes for updating a bot's guild count on several bot list services."""
from __future__ import annotations

__all__: list[str] = [
    "AbstractCountStrategy",
    "AbstractManager",
    "BotsGGService",
    "CacheStrategy",
    "CountUnknownError",
    "DiscordBotListService",
    "EventStrategy",
    "SakeStrategy",
    "ServiceManager",
    "ServiceSig",
    "TopGGService",
]

import abc
import asyncio
import datetime
import logging
import time
import typing
from collections import abc as collections

import aiohttp
import hikari
import hikari.api
import hikari.snowflakes

from . import _internal
from . import backoff

if typing.TYPE_CHECKING:
    import sake
    from hikari import traits
    from typing_extensions import Self

    _T = typing.TypeVar("_T")
    _EventT = typing.TypeVar("_EventT", bound=hikari.Event)
    _ServiceSigT = typing.TypeVar("_ServiceSigT", bound="ServiceSig")
    _LoadableStrategyT = typing.TypeVar("_LoadableStrategyT", bound="_LoadableStrategy")


_LOGGER = logging.getLogger("hikari.yuyo")
_strategies: list[type[_LoadableStrategy]] = []
_DEFAULT_USER_AGENT = "Yuyo.last_status"
_RATE_LIMITED_STATUS = 429
_RETRY_AFTER_KEY = "Retry-After"
_RETRY_ERROR_CODES = frozenset((_RATE_LIMITED_STATUS, 500, 502, 503, 504))
_USER_AGENT = _DEFAULT_USER_AGENT + " (Bot:{})"

ServiceSig = collections.Callable[["AbstractManager"], collections.Coroutine[typing.Any, typing.Any, None]]
"""Signature of a callback used to update a service."""


class _InvalidStrategyError(TypeError):
    """Error raised by spawn when the strategy isn't valid for the provided manager."""


class CountUnknownError(RuntimeError):
    """Error raised when the count is currently unknown."""


class AbstractCountStrategy(abc.ABC):
    """Protocol of a class used for calculating the bot's guild count."""

    __slots__ = ()

    @property
    @abc.abstractmethod
    def is_shard_bound(self) -> bool:
        """Whether this count is just for the current shards."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Close the counter."""

    @abc.abstractmethod
    async def open(self) -> None:
        """Open the counter."""

    @abc.abstractmethod
    async def count(self) -> typing.Union[int, collections.Mapping[int, int]]:
        """Get a possibly cached guild count from this counter.

        Returns
        -------
        int
            The current guild count(s).

            If this is an int then this is a global count.
            If this is a mapping then this is shard-specific counts.

        Raises
        ------
        CountUnknownError
            If the count is currently unknown.
        """


class _LoadableStrategy(AbstractCountStrategy, abc.ABC):
    """ABC of a count strategy which can be automatically loaded."""

    __slots__ = ()

    @classmethod
    @abc.abstractmethod
    def spawn(cls, manager: AbstractManager, /) -> Self:
        """Spawn a counter for a specific manager.

        Parameters
        ----------
        manager
            Object of the manager this counter is being spawned for.

        Returns
        -------
        Self
            The spawned counter.

        Raises
        ------
        _InvalidStrategyError
            If this strategy wouldn't be able to accurately get a guild count
            with the provided manager and it's resources.
        """


def _as_strategy(strategy: type[_LoadableStrategyT], /) -> type[_LoadableStrategyT]:
    _strategies.append(strategy)
    return strategy


@_as_strategy
class CacheStrategy(_LoadableStrategy):
    """Cache based implementation of [yuyo.list_status.AbstractCountStrategy][].

    !!! warning
        This will only function properly if GUILD intents are declared
        and the guild cache resource is enabled.
    """

    __slots__ = ("_cache", "_shards")

    def __init__(self, cache: hikari.api.Cache, shards: hikari.ShardAware, /) -> None:
        """Initialise a cache strategy.

        Parameters
        ----------
        cache
            The cache object this should use for getting the guild count.
        shards
            The shard aware client this should use for grouping counts per-shard.
        """
        self._cache = cache
        self._shards = shards

    @property
    def is_shard_bound(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def open(self) -> None:
        return None

    async def count(self) -> collections.Mapping[int, int]:
        return _shard_guild_ids(self._shards, self._cache.get_guilds_view().keys())

    @classmethod
    def spawn(cls, manager: AbstractManager, /) -> CacheStrategy:
        if not manager.cache or not manager.shards:
            raise _InvalidStrategyError

        cache_enabled = manager.cache.settings.components & hikari.api.CacheComponents.GUILDS
        shard_enabled = manager.shards.intents & hikari.Intents.GUILDS
        if not cache_enabled or not shard_enabled:
            raise _InvalidStrategyError

        return cls(manager.cache, manager.shards)


class SakeStrategy(AbstractCountStrategy):
    """Async cache based implementation of [yuyo.list_status.AbstractCountStrategy][].

    This relies on [Sake][sake].
    """

    __slots__ = ("_cache", "_is_shard_bound")

    def __init__(self, cache: sake.abc.GuildCache, /) -> None:
        r"""Initialise a Sake strategy.

        Unlike [CacheStrategy][yuyo.list_status.CacheStrategy] and
        [EventStrategy][yuyo.list_status.EventStrategy] this strategy must be
        directly initialised and passed to [ServiceManager.\_\_init\_\_][yuyo.list_status.ServiceManager]
        as `strategy=`.

        Parameters
        ----------
        cache
            The Sake guild cache to use to get the guild count.
        """
        self._cache = cache

    @property
    def is_shard_bound(self) -> bool:
        return False

    async def close(self) -> None:
        return None

    async def open(self) -> None:
        return None

    async def count(self) -> int:
        import sake

        try:
            return await self._cache.iter_guilds().len()
        except sake.ClosedClient:
            _LOGGER.warning("Couldn't get guild count from closed Sake cache")
            raise CountUnknownError from None


@_as_strategy
class EventStrategy(_LoadableStrategy):
    """Cache based implementation of [yuyo.list_status.AbstractCountStrategy][].

    !!! warning
        This will only function properly if GUILD intents are declared.
    """

    __slots__ = ("_event_manager", "_guild_ids", "_shards", "_started")

    def __init__(self, event_manager: hikari.api.EventManager, shards: hikari.ShardAware, /) -> None:
        """Initialise an event etrategy.

        !!! note
            You usually won't need to initialise this yourself as
            [yuyo.list_status.ServiceManager][] will automatically pick this
            strategy if the bot config matches it.

        Parameters
        ----------
        event_manager
            The event manager this should use to track shard guild counts.
        shards
            The shard manager this should use to track shard guild counts.
        """
        self._event_manager = event_manager
        self._guild_ids: set[hikari.Snowflake] = set()
        self._shards = shards
        self._started = False

    @property
    def is_shard_bound(self) -> bool:
        return True

    async def _on_shard_ready_event(self, event: hikari.ShardReadyEvent, /) -> None:
        for guild_id in event.unavailable_guilds:
            self._guild_ids.add(guild_id)

    async def _on_starting_event(self, _: hikari.StartingEvent, /) -> None:
        self._guild_ids.clear()

    async def _on_guild_available_event(self, event: hikari.GuildAvailableEvent) -> None:
        self._guild_ids.add(event.guild_id)

    async def _on_guild_leave_event(self, event: hikari.GuildLeaveEvent) -> None:
        try:
            self._guild_ids.remove(event.guild_id)
        except KeyError:
            pass

    async def _on_guild_update_event(self, event: hikari.GuildUpdateEvent, /) -> None:
        self._guild_ids.add(event.guild_id)

    def _try_unsubscribe(
        self,
        event_type: type[_EventT],
        callback: collections.Callable[[_EventT], collections.Coroutine[typing.Any, typing.Any, None]],
    ) -> None:
        try:
            self._event_manager.unsubscribe(event_type, callback)

        except (ValueError, LookupError):
            pass

    async def close(self) -> None:
        if not self._started:
            return

        self._started = False
        self._try_unsubscribe(hikari.ShardReadyEvent, self._on_shard_ready_event)
        self._try_unsubscribe(hikari.StartingEvent, self._on_starting_event)
        self._try_unsubscribe(hikari.GuildAvailableEvent, self._on_guild_available_event)
        self._try_unsubscribe(hikari.GuildLeaveEvent, self._on_guild_leave_event)
        self._try_unsubscribe(hikari.GuildUpdateEvent, self._on_guild_update_event)
        self._guild_ids.clear()

    async def open(self) -> None:
        if self._started:
            return

        self._started = True
        self._event_manager.subscribe(hikari.ShardReadyEvent, self._on_shard_ready_event)
        self._event_manager.subscribe(hikari.StartingEvent, self._on_starting_event)
        self._event_manager.subscribe(hikari.GuildAvailableEvent, self._on_guild_available_event)
        self._event_manager.subscribe(hikari.GuildLeaveEvent, self._on_guild_leave_event)
        self._event_manager.subscribe(hikari.GuildUpdateEvent, self._on_guild_update_event)

    async def count(self) -> collections.Mapping[int, int]:
        return _shard_guild_ids(self._shards, self._guild_ids)

    @classmethod
    def spawn(cls, manager: AbstractManager, /) -> EventStrategy:
        events = manager.event_manager
        shards = manager.shards
        if not events or not shards or not shards.intents & hikari.Intents.GUILDS:
            raise _InvalidStrategyError

        return cls(events, shards)


def _shard_guild_ids(shards: hikari.ShardAware, guild_ids: collections.Iterable[hikari.Snowflake], /) -> dict[int, int]:
    counts = {shard_id: 0 for shard_id in shards.shards.keys()}

    for guild_id in guild_ids:
        shard_id = hikari.snowflakes.calculate_shard_id(shards.shard_count, guild_id)
        try:
            counts[shard_id] += 1

        except KeyError:
            counts[shard_id] = 1

    return counts


class AbstractManager(typing.Protocol):
    """Abstract class used for managing services."""

    __slots__ = ()

    @property
    @abc.abstractmethod
    def cache(self) -> typing.Optional[hikari.api.Cache]:
        """The cache service this manager is bound to."""

    @property
    @abc.abstractmethod
    def counter(self) -> AbstractCountStrategy:
        """The country strategy this manager was initialised with."""

    @property
    @abc.abstractmethod
    def event_manager(self) -> typing.Optional[hikari.api.EventManager]:
        """The event manager this manager is bound to."""

    @property
    @abc.abstractmethod
    def shards(self) -> typing.Optional[hikari.ShardAware]:
        """The shard aware client this manager is bound to."""

    @property
    @abc.abstractmethod
    def rest(self) -> hikari.api.RESTClient:
        """The REST client this manager is bound to."""

    @property
    @abc.abstractmethod
    def user_agent(self) -> str:
        """User agent services within this manager should use for requests."""

    @abc.abstractmethod
    async def get_me(self) -> hikari.User:
        """Get user object of the bot this manager is bound to.

        Returns
        -------
        hikari.users.User
            User object of the bot this manager is bound to.
        """

    @abc.abstractmethod
    def get_session(self) -> aiohttp.ClientSession:
        """Get an aiohttp session to use to make requests within the services.

        Returns
        -------
        aiohttp.ClientSession
            an aiohttp session to use to make requests within the services.

        Raises
        ------
        RuntimeError
            * If this is called in an environment with no running event loop.
            * If the client isn't running.
        """


class _ServiceDescriptor:
    __slots__ = ("repeat", "function")

    def __init__(self, service: ServiceSig, repeat: float, /) -> None:
        self.function = service
        self.repeat = repeat

    def __repr__(self) -> str:
        return f"_ServiceDescriptor <{self.function}, {self.repeat}>"


class ServiceManager(AbstractManager):
    """Standard service manager."""

    __slots__ = (
        "_cache",
        "_counter",
        "_event_manager",
        "_me",
        "_me_lock",
        "_rest",
        "_services",
        "_session",
        "_shards",
        "_task",
        "_user_agent",
    )

    def __init__(
        self,
        rest: hikari.api.RESTClient,
        /,
        *,
        cache: typing.Optional[hikari.api.Cache] = None,
        event_manager: typing.Optional[hikari.api.EventManager] = None,
        shards: typing.Optional[traits.ShardAware] = None,
        event_managed: typing.Optional[bool] = None,
        strategy: typing.Optional[AbstractCountStrategy] = None,
        user_agent: typing.Optional[str] = None,
    ) -> None:
        """Initialise a service manager.

        Parameters
        ----------
        rest
            The RESTAware Hikari client to bind this manager to.
        cache
            The cache aware Hikari client this manager should use.
        event_manager
            The event manager aware Hikari client this manager should use.
        shards
            The shard aware Hikari client this manager should use.
        event_managed
            Whether this client should be automatically opened and closed based
            on `event_manager`'s lifetime events.

            Defaults to [True][] when `event_manager` is passed.
        strategy
            The counter strategy this manager should expose to services.

            If this is left as [None][] then the manager will try to pick
            a suitable standard strategy based on the provided Hikari clients.
        user_agent
            Override the standard user agent used during requests to bot list services.

        Raises
        ------
        ValueError
            If the manager failed to find a suitable standard strategy to use
            when `strategy` was left as [None][].

            If `event_managed` is passed as [True][] when `event_manager` is [None][].
        """
        self._cache = cache
        self._event_manager = event_manager
        self._rest = rest
        self._services: list[_ServiceDescriptor] = []
        self._session: typing.Optional[aiohttp.ClientSession] = None
        self._shards = shards
        self._task: typing.Optional[asyncio.Task[None]] = None
        self._me: typing.Optional[hikari.OwnUser] = None
        self._me_lock: typing.Optional[asyncio.Lock] = None
        self._user_agent = user_agent

        if strategy:
            self._counter = strategy

        else:
            for strategy_ in _strategies:
                try:
                    self._counter = strategy_.spawn(self)
                    break

                except _InvalidStrategyError:
                    pass

            else:
                raise ValueError("Cannot find a valid guild counting strategy for the provided Hikari client(s)")

        if event_managed or event_managed is None and event_manager:
            if not event_manager:
                raise ValueError("event_managed may only be passed when an event_manager is also passed")

            event_manager.subscribe(hikari.StartingEvent, self._on_starting_event)
            event_manager.subscribe(hikari.StoppingEvent, self._on_stopping_event)

        if self._counter.is_shard_bound and not self._shards:
            raise ValueError("Cannot use a shard bound strategy without shards present")

    @classmethod
    def from_gateway_bot(
        cls,
        bot: _internal.GatewayBotProto,
        /,
        *,
        event_managed: bool = True,
        strategy: typing.Optional[AbstractCountStrategy] = None,
        user_agent: typing.Optional[str] = None,
    ) -> ServiceManager:
        """Build a service manager from a gateway bot.

        Parameters
        ----------
        bot : hikari.traits.ShardAware & hikari.traits.RESTAware & hikari.traits.EventManagerAware
            The gateway bot to build a service manager from.
        event_managed
            Whether this client should be automatically opened and closed based
            on `bot`'s lifetime events.
        strategy
            The counter strategy this manager should expose to services.

            If this is left as [None][] then the manager will try to pick
            a suitable standard strategy based on the provided Hikari clients.
        user_agent
            Override the standard user agent used during requests to bot list services.

        Returns
        -------
        ServiceManager
            The build service manager.

        Raises
        ------
        ValueError
            If the manager failed to find a suitable standard strategy to use
            when `strategy` was left as [None][].
        """
        return cls(
            bot.rest,
            cache=bot.cache if isinstance(bot, hikari.CacheAware) else None,
            event_manager=bot.event_manager,
            event_managed=event_managed,
            shards=bot,
            strategy=strategy,
            user_agent=user_agent,
        )

    @property
    def is_alive(self) -> bool:
        """Wwhether this manager is active."""
        return self._task is not None

    @property
    def cache(self) -> typing.Optional[hikari.api.Cache]:
        return self._cache

    @property
    def counter(self) -> AbstractCountStrategy:
        return self._counter

    @property
    def event_manager(self) -> typing.Optional[hikari.api.EventManager]:
        return self._event_manager

    @property
    def rest(self) -> hikari.api.RESTClient:
        return self._rest

    @property
    def shards(self) -> typing.Optional[traits.ShardAware]:
        return self._shards

    @property
    def services(self) -> collections.Sequence[ServiceSig]:
        return [service.function for service in self._services]

    @property
    def user_agent(self) -> str:
        return self._user_agent or _DEFAULT_USER_AGENT

    async def _on_starting_event(self, _: hikari.StartingEvent, /) -> None:
        await self.open()

    async def _on_stopping_event(self, _: hikari.StoppingEvent, /) -> None:
        await self.close()

    def add_service(
        self,
        service: ServiceSig,
        /,
        *,
        repeat: typing.Union[datetime.timedelta, int, float] = datetime.timedelta(hours=1),
    ) -> Self:
        """Add a service to this manager.

        Parameters
        ----------
        service
            Asynchronous callback used to update this service.
        repeat
            How often this service should be updated in seconds.

        Returns
        -------
        Self
            Object of this service manager.

        Raises
        ------
        ValueError
            If repeat is less than 1 second.
        RuntimeError
            If the client is already running.
        """
        if self._task:
            raise RuntimeError("Cannot add a service to an already running manager")

        if isinstance(repeat, datetime.timedelta):
            float_repeat = repeat.total_seconds()

        else:
            float_repeat = float(repeat)

        if float_repeat < 1:
            raise ValueError("Repeat cannot be under 1 second")

        _queue_insert(self._services, lambda s: s.repeat > float_repeat, _ServiceDescriptor(service, float_repeat))
        return self

    def remove_service(self, service: ServiceSig, /) -> None:
        """Remove the first found entry of the registered service.

        Parameters
        ----------
        service
            Service callback to unregister.

        Raises
        ------
        RuntimeError
            If called while the manager is active.
        ValueError
            If the service callback isn't found.
        """
        if self._task:
            raise RuntimeError("Cannot remove a service while this manager is running")

        for descriptor in self._services.copy():
            if descriptor.function == service:
                self._services.remove(descriptor)
                break

        else:
            raise ValueError("Couldn't find service")

    def with_service(
        self, *, repeat: typing.Union[datetime.timedelta, int, float] = datetime.timedelta(hours=1)
    ) -> collections.Callable[[_ServiceSigT], _ServiceSigT]:
        """Add a service to this manager by decorating a function.

        Parameters
        ----------
        repeat
            How often this service should be updated in seconds.

        Returns
        -------
        collections.abc.Callable[[ServiceSig], ServiceSig]
            Decorator callback used to add a service.

        Raises
        ------
        ValueError
            If repeat is less than 1 second.
        RuntimeError
            If the client is already running.
        """

        def decorator(service: _ServiceSigT, /) -> _ServiceSigT:
            self.add_service(service, repeat=repeat)
            return service

        return decorator

    async def close(self) -> None:
        """Close this manager."""
        if not self._task:
            return

        self._task.cancel()
        self._task = None
        await self._counter.close()

        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def open(self) -> None:
        """Start this manager.

        Raises
        ------
        RuntimeError
            If this manager is already running.
        """
        if not self._services:
            raise RuntimeError("Cannot run a client with no registered services.")

        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()

        if not self._task:
            await self._counter.open()
            self._task = asyncio.create_task(self._loop())

    async def get_me(self) -> hikari.User:
        if self._me:
            return self._me

        if self._cache:
            self._me = self._cache.get_me()

        if not self._me:
            if not self._me_lock:
                self._me_lock = asyncio.Lock()

            async with self._me_lock:
                self._me = await self._rest.fetch_my_user()

        if not self._user_agent:
            self._user_agent = _USER_AGENT.format(self._me)

        return self._me

    def get_session(self) -> aiohttp.ClientSession:
        if not self._session:
            raise RuntimeError("Client is currently inactive")

        # Asserts that this is only called within a running event loop.
        asyncio.get_running_loop()
        if self._session.closed:
            self._session = aiohttp.ClientSession()

        return self._session

    async def _loop(self) -> None:
        # This acts as a priority queue.
        queue: list[tuple[float, _ServiceDescriptor]] = [(service.repeat, service) for service in self._services]
        while True:
            await asyncio.sleep(sleep := queue[0][0])
            queue = [(time_ - sleep, service) for time_, service in queue]

            while queue[0][0] <= 0:
                service = queue.pop(0)[1]
                time_taken = time.perf_counter()

                try:
                    await service.function(self)

                except CountUnknownError:
                    pass

                except Exception as exc:
                    _LOGGER.exception(
                        "Service call to %r service raised an unexpected exception", service.function, exc_info=exc
                    )

                time_taken = time.perf_counter() - time_taken
                queue = [(time_ - time_taken, service) for time_, service in queue]
                _queue_insert(queue, lambda s: s[0] > service.repeat, (service.repeat, service))


def _queue_insert(sequence: list[_T], check: collections.Callable[[_T], bool], value: _T, /) -> None:
    # As we rely on order here for queueing calls we have a dedicated method for inserting based on time left.
    index: int = -1
    for index, sub_value in enumerate(sequence):
        if check(sub_value):
            break

    else:
        index += 1

    sequence.insert(index, value)


async def _log_response(service_name: str, response: aiohttp.ClientResponse, /, *, is_global: bool = True) -> None:
    if response.status < 300:
        _LOGGER.info("Posted bot's stats to %s for the ", service_name, "whole bot" if is_global else "local shards")
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

    elif response.status == 401:
        _LOGGER.warning("%s returned a 401, are you sure you provided the right token? %r", service_name, content)

    elif response.status == _RATE_LIMITED_STATUS:
        _LOGGER.warning("Hit ratelimit while trying to post bot's stats to %s: %r", service_name, content)

    else:
        _LOGGER.exception(
            "Couldn't post bot's stats to %s due to making a malformed request "
            "(%s), is your version of Yuyo up to date? %r",
            service_name,
            response.status,
            content,
        )


class TopGGService:
    """<https://top.gg> status update service."""

    __slots__ = ("_token",)

    def __init__(self, token: str, /) -> None:
        """Initialise a top.gg service.

        Parameters
        ----------
        token
            Authorization token used to update the bot's status.
        """
        self._token = token

    async def __call__(self, client: AbstractManager, /) -> None:
        counts = await client.counter.count()
        me = await client.get_me()
        headers = {"Authorization": self._token, "User-Agent": client.user_agent}
        session = client.get_session()
        url = f"https://top.gg/api/bots/{me.id}/stats"

        if isinstance(counts, int):
            is_global = True
            json: dict[str, typing.Union[int, list[int]]] = {"server_count": counts}

        else:
            if not client.shards:
                raise RuntimeError("Shard count unknown")

            _LOGGER.debug("Fetching stats from Top.GG")
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                raw_shards: typing.Optional[list[str]] = (await response.json()).get("shards")

            is_global = False
            shards = {index: int(count) for index, count in enumerate(raw_shards or ())}
            shards.update(counts)
            json = {"shards": [shards.get(shard_id, 0) for shard_id in range(client.shards.shard_count)]}

        if client.shards:
            json["shard_count"] = client.shards.shard_count

        async with session.post(url, headers=headers, json=json) as response:
            await _log_response("Top.GG", response, is_global=is_global)


class BotsGGService:
    """<https://discord.bots.gg> status update service."""

    __slots__ = ("_token",)

    def __init__(self, token: str, /) -> None:
        """Initialise a bots.gg service.

        Parameters
        ----------
        token
            Authorization token used to update the bot's status.
        """
        self._token = token

    async def __call__(self, client: AbstractManager, /) -> None:
        counts = await client.counter.count()
        me = await client.get_me()
        headers = {"Authorization": self._token, "User-Agent": client.user_agent}
        session = client.get_session()

        if isinstance(counts, int):
            json: dict[str, typing.Union[int, list[dict[str, int]]]] = {"guildCount": counts}
            is_global = True

        else:
            json = {"shards": [{"shardId": shard_id, "guildCount": count} for shard_id, count in counts.items()]}
            is_global = False

        if client.shards:
            json["shardCount"] = client.shards.shard_count

        async with session.post(
            f"https://discord.bots.gg/api/v1/bots/{me.id}/stats", headers=headers, json=json
        ) as response:
            await _log_response("Bots.GG", response, is_global=is_global)


class DiscordBotListService:
    """<https://discordbotlist.com> status update service."""

    __slots__ = ("_token",)

    def __init__(self, token: str, /) -> None:
        """Initialise a discordbotlist.com service.

        Parameters
        ----------
        token
            Authorization token used to update the bot's status.
        """
        self._token = token

    async def __call__(self, client: AbstractManager, /) -> None:
        counts = await client.counter.count()
        if isinstance(counts, int):
            await self._post(client, counts)
            return

        back_off = backoff.Backoff()
        for shard_id, count in counts.items():
            async for retry in back_off:
                _LOGGER.debug("Posting stats to DiscordBotList for shard %s; attempt %s", shard_id, retry + 1)
                retry_after = await self._post(client, count, shard_id=shard_id)
                if retry_after is None:
                    _LOGGER.info("Posted stats to DiscordBotList for shard %s", shard_id)
                    break

                elif retry_after != -1:
                    back_off.set_next_backoff(retry_after)
                    _LOGGER.info("Rate-limited on posting stats to DiscordBotList, retrying in %s seconds", retry_after)

                else:
                    _LOGGER.info("Rate-limited on posting stats to DiscordBotList, retrying soon")

            back_off.reset()

    async def _post(
        self, client: AbstractManager, count: int, /, *, shard_id: typing.Optional[int] = None
    ) -> typing.Optional[int]:
        headers = {"Authorization": self._token, "User-Agent": client.user_agent}
        json = {"guilds": count}
        me = await client.get_me()
        session = client.get_session()

        if shard_id is not None:
            json["shard_id"] = shard_id

        async with session.post(
            f"https://discordbotlist.com/api/v1/bots/{me.id}/stats", headers=headers, json=json
        ) as response:
            if shard_id is None:
                await _log_response("Discordbotlist.com", response, is_global=False)
                return None  # MyPy compatibility

            if response.status in _RETRY_ERROR_CODES:
                if retry_after := response.headers.get(_RETRY_AFTER_KEY):
                    return int(retry_after)

                return -1

            response.raise_for_status()

        return None  # MyPy compatibility
