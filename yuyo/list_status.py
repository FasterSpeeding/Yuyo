# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020-2021, Faster Speeding
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

__all__: typing.Sequence[str] = [
    "BotsGGService",
    "CacheStrategy",
    "CountStrategyProto",
    "EventStrategy",
    "InvalidStrategyError",
    "ManagerProto",
    "ServiceManager",
    "TopGGService",
]

import asyncio
import datetime
import logging
import time
import typing

import aiohttp
import hikari
import hikari.api

# from . import __version__
from . import backoff

if typing.TYPE_CHECKING:
    from hikari import traits

    _ServiceManagerT = typing.TypeVar("_ServiceManagerT", bound="ServiceManager")
    _ValueT = typing.TypeVar("_ValueT")
    _EventT = typing.TypeVar("_EventT", bound=hikari.Event)
    _ServiceSigT = typing.TypeVar("_ServiceSigT", bound="ServiceSig")
    _StrategyT = typing.TypeVar("_StrategyT", bound="CountStrategyProto")


_LOGGER = logging.getLogger("hikari.yuyo")
_strategies: typing.List[typing.Type[CountStrategyProto]] = []
_DEFAULT_USER_AGENT = "Yuyo.last_status"  # f"/{__version__}"
_USER_AGENT = _DEFAULT_USER_AGENT + " (Bot:{})"

ServiceSig = typing.Callable[["ManagerProto"], typing.Coroutine[typing.Any, typing.Any, None]]


def _as_strategy(strategy: typing.Type[_StrategyT]) -> typing.Type[_StrategyT]:
    _strategies.append(strategy)
    return strategy


class InvalidStrategyError(TypeError):
    """Error raised by spawn when the strategy isn't valid for the provided manager."""


class CountStrategyProto(typing.Protocol):
    """Protocol of a class used for calculating the bot's guild count."""

    __slots__ = ()

    async def close(self) -> None:
        """Close the counter."""
        raise NotImplementedError

    async def open(self) -> None:
        """Open the counter."""
        raise NotImplementedError

    async def count(self) -> int:
        """Get a possibly cached guild count from this counter."""
        raise NotImplementedError

    @classmethod
    def spawn(cls: typing.Type[_StrategyT], manager: ManagerProto, /) -> _StrategyT:
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
        InvalidStrategyError
            If this strategy wouldn't be able to accurately get a guild count
            with the provided manager and it's resources.
        """
        raise NotImplementedError


@_as_strategy
class CacheStrategy(CountStrategyProto):
    """Cache based implementation of `CountStrategyProto`.

    !!! warning
        This will only function properly if GUILD intents are declared
        and the guild cache resource is enabled.
    """

    __slots__ = ("_cache",)

    def __init__(self, cache: hikari.api.Cache) -> None:
        self._cache = cache

    async def close(self) -> None:
        return None

    async def open(self) -> None:
        return None

    async def count(self) -> int:
        return len(self._cache.get_guilds_view())

    @classmethod
    def spawn(cls, manager: ManagerProto, /) -> CacheStrategy:
        if not manager.cache or not manager.shards:
            raise InvalidStrategyError

        cache_enabled = manager.cache.settings.components & hikari.api.CacheComponents.GUILDS
        shard_enabled = manager.shards.intents & hikari.Intents.GUILDS
        if not cache_enabled or not shard_enabled:
            raise InvalidStrategyError

        return cls(manager.cache)


@_as_strategy
class EventStrategy(CountStrategyProto):
    """Cache based implementation of `CountStrategyProto`.

    !!! warning
        This will only function properly if GUILD intents are declared.
    """

    __slots__ = ("_event_manager", "_guild_ids", "_shards", "_started")

    def __init__(self, event_manager: hikari.api.EventManager, shards: hikari.ShardAware) -> None:
        self._event_manager = event_manager
        self._guild_ids: typing.Set[hikari.Snowflake] = set()
        self._shards = shards
        self._started = False

    async def _on_shard_ready_event(self, event: hikari.ShardReadyEvent, /) -> None:
        for guild_id in event.unavailable_guilds:
            self._guild_ids.add(guild_id)

    async def _on_starting_event(self, _: hikari.StartingEvent, /) -> None:
        self._guild_ids.clear()

    async def _on_guild_visibility_event(self, event: hikari.GuildVisibilityEvent, /) -> None:
        if isinstance(event, hikari.GuildAvailableEvent):
            self._guild_ids.add(event.guild_id)

        elif isinstance(event, hikari.GuildLeaveEvent):
            self._guild_ids.remove(event.guild_id)

    async def _on_guild_update_event(self, event: hikari.GuildUpdateEvent, /) -> None:
        self._guild_ids.add(event.guild_id)

    def _try_unsubscribe(
        self,
        event_type: typing.Type[_EventT],
        callback: typing.Callable[[_EventT], typing.Coroutine[typing.Any, typing.Any, None]],
    ) -> None:
        try:
            self._event_manager.unsubscribe(event_type, callback)

        except (ValueError, LookupError):
            pass

    async def close(self) -> None:
        if not self._started:
            return

        self._try_unsubscribe(hikari.ShardReadyEvent, self._on_shard_ready_event)
        self._try_unsubscribe(hikari.StartingEvent, self._on_starting_event)
        self._try_unsubscribe(hikari.GuildVisibilityEvent, self._on_guild_visibility_event)
        self._try_unsubscribe(hikari.GuildUpdateEvent, self._on_guild_update_event)
        self._guild_ids.clear()

    async def open(self) -> None:
        if self._started:
            return

        self._event_manager.subscribe(hikari.ShardReadyEvent, self._on_shard_ready_event)
        self._event_manager.subscribe(hikari.StartingEvent, self._on_starting_event)
        self._event_manager.subscribe(hikari.GuildVisibilityEvent, self._on_guild_visibility_event)
        self._event_manager.subscribe(hikari.GuildUpdateEvent, self._on_guild_update_event)

    async def count(self) -> int:
        return len(self._guild_ids)

    @classmethod
    def spawn(cls, manager: ManagerProto, /) -> EventStrategy:
        events = manager.event_manager
        shards = manager.shards
        if not events or not shards or not (shards.intents & hikari.Intents.GUILDS) == hikari.Intents.GUILDS:
            raise InvalidStrategyError

        return cls(events, shards)


class ManagerProto(typing.Protocol):
    """Protocol of the class responsible for managing services."""

    __slots__ = ()

    @property
    def cache(self) -> typing.Optional[hikari.api.Cache]:
        """The cache service this manager is bound to."""
        raise NotImplementedError

    @property
    def counter(self) -> CountStrategyProto:
        """The country strategy this manager was initialised with."""
        raise NotImplementedError

    @property
    def event_manager(self) -> typing.Optional[hikari.api.EventManager]:
        """The event manager this manager is bound to."""
        raise NotImplementedError

    @property
    def shards(self) -> typing.Optional[hikari.ShardAware]:
        """The shard aware client this manager is bound to."""
        raise NotImplementedError

    @property
    def rest(self) -> hikari.api.RESTClient:
        """The REST client this manager is bound to."""
        raise NotImplementedError

    @property
    def user_agent(self) -> str:
        """User agent services within this manager should use for requests."""
        raise NotImplementedError

    async def get_me(self) -> hikari.User:
        """Get user object of the bot this manager is bound to.

        Returns
        -------
        hikari.users.User
            User object of the bot this manager is bound to.
        """
        raise NotImplementedError

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
        raise NotImplementedError


class _ServiceDescriptor:
    __slots__ = ("repeat", "function")

    def __init__(self, service: ServiceSig, repeat: float, /) -> None:
        self.function = service
        self.repeat = repeat

    def __repr__(self) -> str:
        return f"_ServiceDescriptor <{self.function}, {self.repeat}>"


class ServiceManager(ManagerProto):
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
        strategy: typing.Optional[CountStrategyProto] = None,
        user_agent: typing.Optional[str] = None,
    ) -> None:
        """Initialise a service manager.

        Parameters
        ----------
        rest
            The RESTAware Hikari client to bind this manager to.
        cache
            The cache aware Hikari client this manager should use.
        event_manger
            The event manager aware Hikari client this manager should use.
        shards
            The shard aware Hikari client this manager should use.
        event_managed
            Whether this client should be automatically opened and closed based
            on `event_manger`'s lifetime events.
            Defaults to `True` when `event_manager` is passed.
        strategy
            The counter strategy this manager should expose to services.

            If this is left as `None` then the manager will try to pick
            a suitable standard strategy based on the provided Hikari clients.
        user_agent
            Override the standard user agent used during requests to bot list services.

        Raises
        ------
        ValueError
            If the manager failed to find a suitable standard strategy to use
            when `strategy` was left as `None`.

            If `event_managed` is passed as `True` when `event_manager` is None.
        """
        self._cache = cache
        self._event_manager = event_manager
        self._rest = rest
        self._services: typing.List[_ServiceDescriptor] = []
        self._session: typing.Optional[aiohttp.ClientSession] = None
        self._shards = shards
        self._task: typing.Optional[asyncio.Task[None]] = None
        self._me = (cache and cache.get_me()) or None
        self._me_lock: typing.Optional[asyncio.Lock] = None
        self._user_agent = user_agent

        if strategy:
            self._counter = strategy
            return

        for strategy_ in _strategies:
            try:
                self._counter = strategy_.spawn(self)
                break

            except InvalidStrategyError:
                pass

        else:
            raise ValueError("Cannot find a valid guild counting strategy for the provided Hikari client(s)")

        if event_managed or event_managed is None and event_manager:
            if not event_manager:
                raise ValueError("event_managed may only be passed when an event_manager is also passed")

            event_manager.subscribe(hikari.StartingEvent, self._on_starting)
            event_manager.subscribe(hikari.StoppingEvent, self._on_stopping)

    @classmethod
    def from_gateway_bot(
        cls,
        bot: traits.GatewayBotAware,
        /,
        *,
        event_managed: bool = True,
        strategy: typing.Optional[CountStrategyProto] = None,
        user_agent: typing.Optional[str] = None,
    ) -> ServiceManager:
        """Build a service manager from a gateway bot.

        Parameters
        ----------
        bot
            The gateway bot to build a service manager from.
        event_managed
            Whether this client should be automatically opened and closed based
            on `bot`'s lifetime events.
            Defaults to `True`.
        strategy
            The counter strategy this manager should expose to services.

            If this is left as `None` then the manager will try to pick
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
            when `strategy` was left as `None`.
        """
        return cls(
            bot.rest,
            cache=bot.cache,
            event_manager=bot.event_manager,
            event_managed=event_managed,
            strategy=strategy,
            user_agent=user_agent,
        )

    @classmethod
    def from_rest_bot(
        cls,
        bot: traits.RESTBotAware,
        /,
        *,
        strategy: typing.Optional[CountStrategyProto] = None,
        user_agent: typing.Optional[str] = None,
    ) -> ServiceManager:
        """Build a service manager from a REST bot.

        Parameters
        ----------
        bot
            The REST bot to build a service manager from.
        strategy
            The counter strategy this manager should expose to services.

            If this is left as `None` then the manager will try to pick
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
            when `strategy` was left as `None`.
        """
        return cls(bot.rest, strategy=strategy, user_agent=user_agent)

    @property
    def is_alive(self) -> bool:
        """Wwhether this manager is active."""
        return self._task is not None

    @property
    def cache(self) -> typing.Optional[hikari.api.Cache]:
        return self._cache

    @property
    def counter(self) -> CountStrategyProto:
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
    def services(self) -> typing.Sequence[ServiceSig]:
        return [service.function for service in self._services]

    @property
    def user_agent(self) -> str:
        return self._user_agent or _DEFAULT_USER_AGENT

    async def _on_starting(self, event: hikari.StartingEvent) -> None:
        await self.open()

    async def _on_stopping(self, event: hikari.StoppingEvent) -> None:
        await self.close()

    def add_service(
        self: _ServiceManagerT, service: ServiceSig, /, repeat: typing.Union[datetime.timedelta, int, float] = 60 * 60
    ) -> _ServiceManagerT:
        """Add a service to this manager.

        Parameters
        ----------
        service
            Asynchronous callback used to update this service.
        repeat
            How often this service should be updated in seconds.

            This defaults to 1 hour.

        Returns
        -------
        ServiceManager
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

        self._queue_insert(self._services, lambda s: s.repeat > float_repeat, _ServiceDescriptor(service, float_repeat))
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
        self, repeat: typing.Union[datetime.timedelta, int, float] = 60 * 60, /
    ) -> typing.Callable[[_ServiceSigT], _ServiceSigT]:
        """Add a service to this manager by decorating a function.

        Parameters
        ----------
        repeat
            How often this service should be updated in seconds.

            This defaults to 1 hour.

        Returns
        -------
        typing.Callable[[ServiceSig], ServiceSig]
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
        if self._task:
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

        if not self._me_lock:
            self._me_lock = asyncio.Lock()

        async with self._me_lock:
            retry = backoff.Backoff()

            async for _ in retry:
                try:
                    self._me = await self._rest.fetch_my_user()
                    break

                except hikari.InternalServerError:
                    continue

                except hikari.RateLimitedError as exc:
                    retry.set_next_backoff(exc.retry_after)

            else:
                self._me = await self._rest.fetch_my_user()

        if not self._user_agent:
            self._user_agent = _USER_AGENT.format(self._me)

        return self._me

    def get_session(self) -> aiohttp.ClientSession:
        # Asserts that this is only called within a running event loop.
        if not self._session:
            raise RuntimeError("Client is currently inactive")

        asyncio.get_running_loop()
        if self._session.closed:
            self._session = aiohttp.ClientSession()

        return self._session

    async def _loop(self) -> None:
        # This acts as a priority queue.
        queue = [(service.repeat, service) for service in self._services]
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
    def _queue_insert(sequence: typing.List[_ValueT], check: typing.Callable[[_ValueT], bool], value: _ValueT) -> None:
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

    elif response.status == 401:
        _LOGGER.warning("%s returned a 401, are you sure you provided the right token? %r", service_name, content)

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


class TopGGService:
    """https://top.gg status update service."""

    __slots__ = ("_token",)

    def __init__(self, token: str, /) -> None:
        self._token = token

    async def update_top_gg(self, client: ManagerProto, /) -> None:
        me = await client.get_me()
        headers = {"Authorization": self._token, "User-Agent": client.user_agent}
        json = {"server_count": await client.counter.count()}

        if client.shards:
            json["shard_count"] = client.shards.shard_count

        session = client.get_session()

        async with session.post(f"https://top.gg/api/bots/{me.id}/stats", headers=headers, json=json) as response:
            await _log_response("Top.GG", response)


class BotsGGService:
    """https://discord.bots.gg status update service."""

    __slots__ = ("_token",)

    def __init__(self, token: str, /) -> None:
        """Initialise a bots.gg service.

        Parameters
        ----------
        token
            Authorization token used to update the bot's status.

        Returns
        -------
        ServiceSig
            The service callback used to update a bot's status on .
        """
        self._token = token

    async def __call__(self, client: ManagerProto, /) -> None:
        me = await client.get_me()
        headers = {"Authorization": self._token, "User-Agent": client.user_agent}
        json = {"guildCount": await client.counter.count()}

        if client.shards:
            json["shardCount"] = client.shards.shard_count

        session = client.get_session()
        async with session.post(
            f"https://discord.bots.gg/api/v1/bots/{me.id}/stats", headers=headers, json=json
        ) as response:
            await _log_response("Bots.GG", response)
