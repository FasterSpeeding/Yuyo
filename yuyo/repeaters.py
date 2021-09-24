"""
Copyright 2021 crazygmr101

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the 
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit 
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the 
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE 
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR 
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR 
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import asyncio
import datetime
import inspect
from typing import Callable, Any, Awaitable, TypeVar, Generic, Optional, List

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
            loop: Optional[asyncio.AbstractEventLoop] = None
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
        await self._before()
        while self._runs_left != 0:
            self._iter += 1
            self._runs_left -= 1
            self._event_loop.create_task(self._wrapped_coro())
            await asyncio.sleep(self._delay)
        await self._after()

    @property
    def iteration_count(self) -> int:
        """
        The iteration this repeater is on
        """
        return self._iter

    def start(self) -> asyncio.Task:
        """
        Start the repeater

        Returns
        ------
        :class:`asyncio.Task`
            The started task
        """
        if self._task is not None and not self._task.done():
            raise RuntimeError("Repeater already running")
        self._task = self._event_loop.create_task(self._loop())
        return self._task

    def stop(self):
        """
        Cancel the repeater
        """
        if self._task is None or self._task.done():
            raise RuntimeError("Repeater not running")
        self._task.cancel()

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
    Sets the exceptions that a task will ignore. If any of these exceptions are encountered, there will be
    nothing printed to console

    Parameters
    ---------
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
    Sets the exceptions that will stop a task. If any of these exceptions are encountered, the task will stop

    Parameters
    ---------
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
        loop: Optional[asyncio.AbstractEventLoop] = None
) -> Callable[[RepeaterFuncT], Repeater[RepeaterFuncT]]:
    """
    Registers a :class:Repeater.

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
            function,
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            run_count=run_count,
            loop=loop
        )

    return decorator
