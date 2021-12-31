# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2021, Faster Speeding
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

import asyncio
import sys
import threading
import typing

import hikari
from hikari.internal import spel

if typing.TYPE_CHECKING:
    import concurrent.futures
    import types

    if sys.version_info >= (3, 10):
        _P = typing.ParamSpec("_P")

    else:
        import typing_extensions

        _P = typing_extensions.ParamSpec("_P")


_T = typing.TypeVar("_T")
_OtherT = typing.TypeVar("_OtherT")
_SyncRestT = typing.TypeVar("_SyncRestT", bound="SyncRest")

_FlattenerResultT = typing.Union[typing.AsyncIterator[_T], typing.Iterable[_T]]

_FlattenerT = typing.Union[
    spel.AttrGetter[_T, _FlattenerResultT[_OtherT]],
    typing.Callable[[_T], _FlattenerResultT[_OtherT]],
]


async def _start_client(client: hikari.impl.RESTClientImpl) -> None:
    client.start()


def _run_loop(client: hikari.impl.RESTClientImpl, loop: asyncio.BaseEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_start_client(client))
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


class SyncRest:
    __slots__ = ("_loop", "_rest", "_thread")

    def __init__(
        self,
        token: str,
        /,
        token_type: typing.Union[str, hikari.TokenType] = hikari.TokenType.BEARER,
        *,
        executor: typing.Optional[concurrent.futures.Executor] = None,
        http_settings: typing.Optional[hikari.HTTPSettings] = None,
        max_rate_limit: float = 300,
        max_retries: int = 3,
        proxy_settings: typing.Optional[hikari.ProxySettings] = None,
        url: typing.Optional[str] = None,
    ) -> None:
        self._loop = asyncio.new_event_loop()
        self._rest = hikari.RESTApp(
            executor=executor,
            http_settings=http_settings,
            max_rate_limit=max_rate_limit,
            max_retries=max_retries,
            proxy_settings=proxy_settings,
            url=url,
        ).acquire(token, token_type)
        self._thread = threading.Thread(target=_run_loop, args=(self.rest, self._loop))

    def __enter__(self: _SyncRestT) -> _SyncRestT:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_val: typing.Optional[BaseException],
        exc_tb: typing.Optional[types.TracebackType],
    ) -> None:
        try:
            self.stop()
        except RuntimeError:
            pass

    @property
    def rest(self) -> hikari.api.RESTClient:
        return self._rest

    def start(self) -> None:
        if self._thread.is_alive():
            raise RuntimeError("Client is already active")

        self._thread.start()

    def stop(self) -> None:
        if not self.rest.is_alive:
            raise RuntimeError("Client isn't active")

        task = self._loop.create_task(self.rest.close())

        def close(_: asyncio.Future[None]) -> None:
            self._loop.stop()

        task.add_done_callback(close)
        self._thread.join()

    def iter_endpoint(self, iterator: hikari.LazyIterator[_T], /) -> SyncIterator[_T]:
        return SyncIterator(self, iterator)

    def make_request(
        self,
        callback: typing.Callable[_P, typing.Coroutine[typing.Any, typing.Any, _T]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _T:
        if not self.rest.is_alive:
            raise RuntimeError("Client isn't active")

        return asyncio.run_coroutine_threadsafe(callback(*args, **kwargs), self._loop).result()

    # e.g.
    # def fetch_messages(
    #     self,
    #     channel: int,
    #     before: hikari.UndefinedOr[hikari.SearchableSnowflakeishOr[hikari.Unique]] = hikari.UNDEFINED,
    #     after: hikari.UndefinedOr[hikari.SearchableSnowflakeishOr[hikari.Unique]] = hikari.UNDEFINED,
    #     around: hikari.UndefinedOr[hikari.SearchableSnowflakeishOr[hikari.Unique]] = hikari.UNDEFINED,
    # ) -> SyncIterator[hikari.Message]:
    #     if not self.rest.is_alive:
    #         raise RuntimeError("Client isn't active")

    #     return self.iter_endpoint(self.rest.fetch_messages(channel, before=before, after=after, around=around))

    # e.g.
    # def send_message(self, channel: int, content: str) -> hikari.Message:
    #     return self.make_request(self.rest.create_message, channel, content)


class SyncIterator(typing.Iterator[_T]):
    __slots__ = ("_client", "_iterator")

    def __init__(self, client: SyncRest, iterator: hikari.LazyIterator[_T], /) -> None:
        self._client = client
        self._iterator = iterator

    def chunk(self, chunk_size: int) -> SyncIterator[typing.Sequence[_T]]:
        """Return results in chunks of up to `chunk_size` amount of entries."""
        return SyncIterator(self._client, self._iterator.chunk(chunk_size))

    def map(self, transformation: typing.Union[typing.Callable[[_T], _OtherT], str], /) -> SyncIterator[_OtherT]:
        """Map the values to a different value."""
        return SyncIterator(self._client, self._iterator.map(transformation))

    def for_each(self, consumer: typing.Callable[[_T], typing.Any], /) -> None:
        """Pass each value to a given consumer immediately."""
        return self._client.make_request(self._iterator.for_each, consumer)

    def filter(
        self,
        *predicates: typing.Union[typing.Tuple[str, typing.Any], typing.Callable[[_T], bool]],
        **attrs: typing.Any,
    ) -> SyncIterator[_T]:
        """Filter the items by one or more conditions."""
        return SyncIterator(self._client, self._iterator.filter(*predicates, **attrs))

    def take_while(
        self,
        *predicates: typing.Union[typing.Tuple[str, typing.Any], typing.Callable[[_T], bool]],
        **attrs: typing.Any,
    ) -> SyncIterator[_T]:
        """Return each item until any conditions fail or the end is reached."""
        return SyncIterator(self._client, self._iterator.take_while(*predicates, **attrs))

    def take_until(
        self,
        *predicates: typing.Union[typing.Tuple[str, typing.Any], typing.Callable[[_T], bool]],
        **attrs: typing.Any,
    ) -> SyncIterator[_T]:
        """Return each item until any conditions pass or the end is reached."""
        return SyncIterator(self._client, self._iterator.take_until(*predicates, **attrs))

    def skip_while(
        self,
        *predicates: typing.Union[typing.Tuple[str, typing.Any], typing.Callable[[_T], bool]],
        **attrs: typing.Any,
    ) -> SyncIterator[_T]:
        """Discard items while all conditions are True."""
        return SyncIterator(self._client, self._iterator.skip_while(*predicates, **attrs))

    def skip_until(
        self,
        *predicates: typing.Union[typing.Tuple[str, typing.Any], typing.Callable[[_T], bool]],
        **attrs: typing.Any,
    ) -> SyncIterator[_T]:
        """Discard items while all conditions are False."""
        return SyncIterator(self._client, self._iterator.skip_until(*predicates, **attrs))

    def enumerate(self, *, start: int = 0) -> SyncIterator[typing.Tuple[int, _T]]:
        """Enumerate the paginated results lazily."""
        return SyncIterator(self._client, self._iterator.enumerate(start=start))

    def limit(self, limit: int, /) -> SyncIterator[_T]:
        """Limit the number of items you receive from this async iterator."""
        return SyncIterator(self._client, self._iterator.limit(limit))

    def skip(self, number: int, /) -> SyncIterator[_T]:
        """Drop the given number of items, then yield anything after."""
        return SyncIterator(self._client, self._iterator.skip(number))

    def next(self) -> _T:
        """Return the next element of this iterator only."""
        return self._client.make_request(self._iterator.next)

    def last(self) -> _T:
        """Return the last element of this iterator only."""
        return self._client.make_request(self._iterator.last)

    def reversed(self) -> SyncIterator[_T]:
        """Return a lazy iterator of the remainder of this iterator's values reversed."""
        return SyncIterator(self._client, self._iterator.reversed())

    def sort(self, *, key: typing.Any = None, reverse: bool = False) -> typing.Sequence[_T]:
        """Collect all results, then sort the collection before returning it."""
        return self._client.make_request(self._iterator.sort, key=key, reverse=reverse)

    def collect(
        self, collector: typing.Callable[[typing.Sequence[_T]], typing.Collection[_T]], /
    ) -> typing.Collection[_T]:
        """Collect the results into a given type and return it."""
        return self._client.make_request(self._iterator.collect, collector)

    def count(self) -> int:
        """Count the number of results."""
        return self._client.make_request(self._iterator.count)

    def flat_map(self, flattener: _FlattenerT[_T, _OtherT], /) -> SyncIterator[_OtherT]:
        """Perform a flat mapping operation."""
        return SyncIterator(self._client, self._iterator.flat_map(flattener))

    def awaiting(self, *, window_size: int = 10) -> SyncIterator[_T]:
        """Await each item concurrently in a fixed size window."""
        return SyncIterator(self._client, self._iterator.awaiting(window_size))

    def __iter__(self) -> SyncIterator[_T]:
        return self

    def __next__(self) -> _T:
        try:
            return self.next()

        except LookupError:
            raise StopIteration from None
