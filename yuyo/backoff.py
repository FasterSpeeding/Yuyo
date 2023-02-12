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
"""Utility used for handling automatic back-off.

This can be used to cover cases such as hitting rate-limits and failed requests.
"""

from __future__ import annotations

__all__: list[str] = ["Backoff", "ErrorManager"]

import asyncio
import random
import typing

from hikari.impl import rate_limits

if typing.TYPE_CHECKING:
    import types
    from collections import abc as collections

    from typing_extensions import Self


class Backoff:
    """Used to exponentially backoff asynchronously.

    This class acts as an asynchronous iterator and can be iterated over to
    provide implicit backoff where for every iteration other than the first
    this will either back off for the time passed to
    [yuyo.backoff.Backoff.set_next_backoff][] if applicable or a time calculated exponentially.

    Each iteration yields the current retry count (starting at 0).

    Examples
    --------
    An example of using this class as an asynchronous iterator may look like
    the following

    ```py
    # While we can directly do `async for _ in Backoff()`, by assigning it to a
    # variable we allow ourself to provide a specific backoff time in some cases.
    backoff = Backoff()
    async for _ in backoff:
        response = await client.fetch(f"https://example.com/{resource_id}")
        if response.status_code == 403:  # Ratelimited
            # If we have a specific backoff time then set it for the next iteration
            backoff.set_next_backoff(response.headers.get("Retry-After"))

        elif response.status_code >= 500:  # Internal server error
            # Else let the iterator calculate an exponential backoff before the next loop.
            pass

        else:
            response.raise_for_status()
            resource = response.json()
            # We need to break out of the iterator to make sure it doesn't backoff again.
            # Alternatively `Backoff.finish()` can be called to break out of the loop.
            break
    ```

    Alternatively you may want to explicitly call [yuyo.backoff.Backoff.backoff][], a
    alternative of the previous example which uses [yuyo.backoff.Backoff.backoff][]
    may look like the following

    ```py
    backoff = Backoff()
    resource = None
    while not resource:
        response = await client.fetch(f"https://example.com/{resource_id}")
        if response == 403  # Ratelimited
            # If we have a specific backoff time then set it for the next iteration.
            backoff.set_next_backoff(response.headers.get("Retry-After"))
            await backoff.backoff()  # We must explicitly backoff in this flow.

        elif response >= 500:  # Internal server error
            # Else let the iterator calculate an exponential backoff and explicitly backoff.
            await backoff.backoff()

        else:
            response.raise_for_status()
            resource = response.json()
    ```
    """

    __slots__ = ("_backoff", "_finished", "_max_retries", "_next_backoff", "_retries", "_started")

    def __init__(
        self,
        max_retries: typing.Optional[int] = None,
        *,
        base: float = 2.0,
        maximum: float = 64.0,
        jitter_multiplier: float = 1.0,
        initial_increment: int = 0,
    ) -> None:
        """Initialise a backoff instance.

        Parameters
        ----------
        max_retries
            The maximum amount of times this should iterate for between resets.

            If left as [None][] then this iterator will be unlimited.
            This must be greater than or equal to 1.
        base
            The base to use.
        maximum
            The max value the backoff can be in a single iteration. Anything above
            this will be capped to this base value plus random jitter.
        jitter_multiplier
            The multiplier for the random jitter.

            Set to `0` to disable jitter.
        initial_increment
            The initial increment to start at.

        Raises
        ------
        ValueError
            If an [int][] that's too big to be represented as a [float][] or a
            non-finite value is passed in place of a field that's annotated as
            [float][] or if `max_retries` is less than `1`.
        """
        if max_retries is not None and max_retries < 1:
            raise ValueError("max_retries must be greater than 1")

        self._backoff = rate_limits.ExponentialBackOff(
            base=base, maximum=maximum, jitter_multiplier=jitter_multiplier, initial_increment=initial_increment
        )
        self._finished = False
        self._max_retries = max_retries
        self._next_backoff: typing.Optional[float] = None
        self._retries = 0
        self._started = False

    def __aiter__(self) -> Backoff:
        return self

    async def __anext__(self) -> int:
        # We don't want to backoff on the first iteration.
        if not self._started:
            self._started = True
            return 0

        result = await self.backoff()
        if result is None:
            raise StopAsyncIteration

        return result

    @property
    def is_depleted(self) -> bool:
        """Whether "max_retries" has been reached.

        This can be used to workout whether the loop was explicitly broken out
        of using [yuyo.backoff.Backoff.finish][]/`break` or if it hit "max_retries".
        """
        return self._max_retries is not None and self._max_retries == self._retries

    async def backoff(self) -> typing.Optional[int]:
        """Sleep for the provided backoff or for the next exponent.

        This provides an alternative to iterating over this class.

        Returns
        -------
        int | None
            Whether this has reached the end of its iteration.

            If this returns [True][] then that call didn't sleep as this has
            been marked as finished or has reached the max retries.
        """
        if self._finished or self.is_depleted:
            return None

        self._started = True
        # We do this even if _next_backoff is set to make sure it's always incremented.
        backoff_ = next(self._backoff)
        if self._next_backoff is not None:
            backoff_ = self._next_backoff + random.random() * self._backoff.jitter_multiplier  # noqa: S311
            self._next_backoff = None

        self._retries += 1
        await asyncio.sleep(backoff_)
        return self._retries

    def finish(self) -> None:
        """Mark the iterator as finished to break out of the current loop."""
        self._finished = True

    def reset(self) -> None:
        """Reset the backoff to it's original state to reuse it."""
        self._backoff.reset()
        self._finished = False
        self._next_backoff = None
        self._retries = 0
        self._started = False

    def set_next_backoff(self, backoff_: typing.Union[float, int, None], /) -> None:
        """Specify a backoff time for the next iteration or [yuyo.backoff.Backoff.backoff][] call.

        If this is called then the exponent won't be increased for this iteration.

        !!! note
            Calling this multiple times in a single iteration will overwrite any
            previously set next backoff.

        Parameters
        ----------
        backoff_
            The amount of time to backoff for in seconds.

            If this is [None][] then any previously set next backoff will be unset.
        """
        # TODO: maximum?
        self._next_backoff = None if backoff_ is None else float(backoff_)


class ErrorManager:
    """A context manager provided to allow for more concise error handling with [yuyo.backoff.Backoff][].

    Examples
    --------
    The following is an example of using [yuyo.backoff.ErrorManager][] alongside
    [yuyo.backoff.Backoff][] in-order to handle the exceptions which may be raised
    while trying to reply to a message.

    ```py
    retry = Backoff()
    # Rules can either be passed to `ErrorManager`'s initiate as variable arguments
    # or one at a time to `ErrorManager.with_rule` through possibly chained-calls.
    error_handler = (
        # For the 1st rule we catch two errors which would indicate the bot
        # no-longer has access to the target channel and break out of the
        # retry loop using `Backoff.retry`.
        ErrorManager(((NotFoundError, ForbiddenError), lambda _: retry.finish()))
            # For the 2nd rule we catch rate limited errors and set their
            # `retry` value as the next backoff time before suppressing the
            # error to allow this to retry the request.
            .with_rule((RateLimitedError,), lambda exc: retry.set_next_backoff(exc.retry_after))
            # For the 3rd rule we suppress the internal server error to allow
            # backoff to reach the next retry and exponentially backoff as we
            # don't have any specific retry time for this error.
            .with_rule((InternalServerError,), lambda _: False)
    )
    async for _ in retry:
        # We entre this context manager each iteration to catch errors before
        # they cause us to break out of the `Backoff` loop.
        with error_handler:
            await post(f"https://example.com/{resource_id}", json={"content": "General Kenobi"})
            # We need to break out of `retry` if this request succeeds.
            break
    ```
    """

    __slots__ = ("_rules",)

    def __init__(
        self,
        *rules: tuple[
            collections.Iterable[type[BaseException]], collections.Callable[[typing.Any], typing.Optional[bool]]
        ],
    ) -> None:
        """Initialise an error manager instance.

        Parameters
        ----------
        *rules
            Rules to initiate this error context manager with.

            These are each a 2-length tuple where the `tuple[0]` is an
            iterable of types of the exceptions this rule should apply to
            and `tuple[1]` is the rule's callback function.

            The callback function will be called with the raised exception when it
            matches one of the passed exceptions for the relevant rule and may
            raise, return [True][] to indicate that the current error should
            be raised outside of the context manager or
            [False][]/[None][] to suppress the current error.
        """
        self._rules = {(tuple(exceptions), callback) for exceptions, callback in rules}

    def __enter__(self) -> ErrorManager:
        return self

    def __exit__(
        self,
        exception_type: typing.Optional[type[BaseException]],
        exception: typing.Optional[BaseException],
        _: typing.Optional[types.TracebackType],
    ) -> typing.Optional[bool]:
        if exception_type is None:
            return None

        assert exception is not None  # This shouldn't ever be None when exception_type isn't None.
        for rule, callback in self._rules:
            if issubclass(exception_type, rule):
                # For this context manager's rules we switch up how returns are handled to let the rules prevent
                # exceptions from being raised outside of the context by default by having `None` and `False` both
                # indicate don't re-raise (suppress) and `True` indicate that it should re-raise.
                return not callback(exception)

        return False

    def clear_rules(self) -> None:
        """Clear the rules registered with this handler."""
        self._rules.clear()

    def add_rule(
        self,
        exceptions: collections.Iterable[type[BaseException]],
        result: collections.Callable[[typing.Any], typing.Optional[bool]],
        /,
    ) -> Self:
        """Add a rule to this exception context manager.

        Parameters
        ----------
        exceptions
            An iterable of types of the exceptions this rule should apply to.
        result
            The function called with the raised exception when it matches one
            of the passed `exceptions`.
            This may raise, return [True][] to indicate that the current
            error should be raised outside of the context manager or
            [False][]/[None][] to suppress the current error.

        Returns
        -------
        Self
            This returns the handler a rule was being added to in-order to
            allow for chained calls.
        """
        self._rules.add((tuple(exceptions), result))
        return self
