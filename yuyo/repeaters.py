# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020-2021, crazygmr101
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

import asyncio
import datetime
import inspect
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Generic
from typing import List
from typing import Optional
from typing import TypeVar

_function = Callable[..., Awaitable[Any]]
RepeaterFuncT = TypeVar("RepeaterFuncT", bound=_function)


class Repeater(Generic[RepeaterFuncT]):
    def __init__(
        self,
        coro: RepeaterFuncT,
        *,
        seconds: Optional[float] = None,
        minutes: Optional[float] = None,
        hours: Optional[float] = None,
        run_count: Optional[int] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        if not (seconds or minutes or hours):
            raise  # TODO: What error should this raise?
        self._delay: float = (hours or 0) * 3600 + (minutes or 0) * 60 + (seconds or 0)
        self._runs_left = run_count or -1
        self._event_loop = loop or asyncio.get_event_loop()
        self._coro = coro
        self._task: Optional[asyncio.Task[None]] = None
        self._iter: int = 0
        self._next_iteration: Optional[datetime.datetime] = None
        self._before: Optional[RepeaterFuncT] = None
        self._after: Optional[RepeaterFuncT] = None
        self.ignored_exceptions: List[type] = []
        self.fatal_exceptions: List[type] = []

    async def _wrapped_coro(self):
        try:
            await self._coro()
        except BaseException as e:  # noqa - I have to
            if type(e) in self.fatal_exceptions:
                self.stop()
                raise
            if type(e) not in self.ignored_exceptions:
                raise

    async def _loop(self):
        if self._before:
            await self._before()
        while self._runs_left != 0:
            self._iter += 1
            self._runs_left -= 1
            self._event_loop.create_task(self._wrapped_coro())
            await asyncio.sleep(self._delay)
        if self._after:
            await self._after()

    @property
    def iteration_count(self) -> int:
        """Return the iteration this repeater is on."""
        return self._iter

    def start(self) -> asyncio.Task:
        """
        Start the repeater.

        Returns
        -------
        :class:`asyncio.Task`
            The started task
        """
        if self._task is not None and not self._task.done():
            raise RuntimeError("Repeater already running")
        self._task = self._event_loop.create_task(self._loop())
        return self._task

    def stop(self):
        """Cancel the repeater."""
        if self._task is None or self._task.done():
            raise RuntimeError("Repeater not running")
        self._task.cancel()
        if self._after:
            self._event_loop.create_task(self._after())

    def with_pre_callback(self, coro: RepeaterFuncT):
        if not inspect.iscoroutinefunction(coro):
            raise TypeError(f"Pre callback must be a coroutine, got {coro.__class__.__name__}.")
        self._before = coro

    def with_post_callback(self, coro: RepeaterFuncT):
        if not inspect.iscoroutinefunction(coro):
            raise TypeError(f"Post callback must be a coroutine, got {coro.__class__.__name__}.")
        self._after = coro


def with_ignored_exceptions(*exceptions: type) -> Callable[[Repeater[RepeaterFuncT]], Repeater[RepeaterFuncT]]:
    """
    Set the exceptions that a task will ignore.

    If any of these exceptions are encountered, there will be nothing printed to console

    Parameters
    ----------
    exceptions
        List of exception types

    Examples
    --------
    ```py
    @yuyo.with_ignored_exceptions(ZeroDivisionError)
    @yuyo.as_repeater(seconds=1)
    async def repeater():
        global run_count
        run_count += 1
        print(f"Run #{run_count}")
    ```
    """
    for exception in exceptions:
        if not issubclass(exception, Exception):
            raise TypeError(f"Ignored exception must derive from Exception, is {exception.__name__}")

    def decorator(repeater: Repeater[RepeaterFuncT]) -> Repeater[RepeaterFuncT]:
        repeater.ignored_exceptions = exceptions
        return repeater

    return decorator


def with_fatal_exceptions(*exceptions: type) -> Callable[[Repeater[RepeaterFuncT]], Repeater[RepeaterFuncT]]:
    """
    Set the exceptions that will stop a task.

    If any of these exceptions are encountered, the task will stop.

    Parameters
    ----------
    exceptions
        List of exception types

    Examples
    --------
    ```py
    @yuyo.with_fatal_exceptions(ZeroDivisionError, RuntimeError)
    @yuyo.as_repeater(seconds=1)
    async def repeater():
        global run_count
        run_count += 1
        print(f"Run #{run_count}")
    ```
    """
    for exception in exceptions:
        if not issubclass(exception, Exception):
            raise TypeError(f"Fatal exception must derive from Exception, is {exception.__name__}")

    def decorator(repeater: Repeater[RepeaterFuncT]) -> Repeater[RepeaterFuncT]:
        repeater.fatal_exceptions = exceptions
        return repeater

    return decorator


def as_repeater(
    *,
    seconds: Optional[float] = None,
    minutes: Optional[float] = None,
    hours: Optional[float] = None,
    run_count: Optional[int] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Callable[[RepeaterFuncT], Repeater[RepeaterFuncT]]:
    """
    Register a :class:Repeater.

    Parameters
    ----------
    seconds : typing.Optional[float]
        The number of seconds between repeater iterations
    minutes : typing.Optional[float]
        The number of minutes between repeater iterations
    hours : typing.Optional[float]
        The number of hours between repeater iterations
    run_count : typing.Optional[int]
        The number of times the repeater should run
    loop : typing.Optional[asyncio.AbstractEventLoop]:
        The event loop to use. If this is unspecified, the repeater defaults to :func:`asyncio.get_event_loop`
    """

    def decorator(function: RepeaterFuncT) -> Repeater[RepeaterFuncT]:
        return Repeater[RepeaterFuncT](
            function, seconds=seconds, minutes=minutes, hours=hours, run_count=run_count, loop=loop
        )

    return decorator
