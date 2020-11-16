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
"""Utility used for handling automatic back-off.

This can be used to cover cases such as hitting rate-limits and failed requests.
"""

from __future__ import annotations

__all__: typing.Sequence[str] = ["Backoff"]

import asyncio
import typing

from hikari.impl import rate_limits


class Backoff:
    """Used to exponentially backoff asynchronously.

    This class acts as an asynchronous iterator and can be iterated over to
    provide implicit backoff where for every iteration other than the first
    this will either back off for the time passed to `Backoff.set_next_backoff`
    if applicable or a time calculated exponentially.

    Parameters
    ----------
    base : builtins.float
        The base to use. Defaults to `2.0`.
    maximum : builtins.float
        The max value the backoff can be in a single iteration. Anything above
        this will be capped to this base value plus random jitter.
    jitter_multiplier : builtins.float
        The multiplier for the random jitter. Defaults to `1.0`.
        Set to `0` to disable jitter.
    initial_increment : builtins.int
        The initial increment to start at. Defaults to `0`.

    Raises
    ------
    ValueError
        If an `builtins.int` that's too big to be represented as a
        `builtins.float` or a non-finite value is passed in place of a field
        that's annotated as `builtins.float`.

    Examples
    --------
    An example of using this class as an asynchronous iterator may look like
    the following

    ```py
    # While we can directly do `async for _ in Backoff()`, by assigning it to a
    # variable we allow ourself to provide a specific backoff time in some cases.
    backoff = Backoff()
    async for _ in backoff:
        try:
            message = await bot.rest.fetch_message(channel_id, message_id)
        except errors.RateLimitedError as exc:
            # If we have a specific backoff time then set it for the next iteration
            backoff.set_next_backoff(exc.retry_after)
        except errors.InternalServerError:
            # Else let the iterator calculate an exponential backoff before the next loop.
            pass
        else:
            # We need to break out of the iterator to make sure it doesn't backoff again.
            # Alternatively `Backoff.finish()` can be called to break out of the loop.
            break
    ```

    Alternatively you may want to explicitly call `Backoff.backoff`, a
    alternative of the previous example which uses `Backoff.backoff` may
    look like the following

    ```py
    backoff = Backoff()
    message: typing.Optional[messages.Message] = None
    while not message:
        try:
            message = await bot.rest.fetch_message(channel_id, message_id)
        except errors.RateLimitedError as exc:
            # If we have a specific backoff time then set it for the next iteration
            await backoff.backoff(exc.retry_after)
        except errors.InternalServerError:
            # Else let the iterator calculate an exponential backoff before the next loop.
            await backoff.backoff()
    ```
    """

    __slots__: typing.Sequence[str] = ("_backoff", "_finished", "_next_backoff", "_started")

    def __init__(
        self, base: float = 2.0, maximum: float = 64.0, jitter_multiplier: float = 1.0, initial_increment: int = 0
    ) -> None:
        self._backoff = rate_limits.ExponentialBackOff(
            base=base, maximum=maximum, jitter_multiplier=jitter_multiplier, initial_increment=initial_increment
        )
        self._finished = False
        self._next_backoff: typing.Optional[float] = None
        self._started = False

    def __aiter__(self) -> Backoff:
        return self

    async def __anext__(self) -> None:
        if self._finished:
            raise StopAsyncIteration

        # We don't want to backoff on the first iteration.
        if not self._started:
            self._started = True
            return

        backoff_: float
        if self._next_backoff is None:
            backoff_ = next(self._backoff)
        else:
            backoff_ = self._next_backoff
            self._next_backoff = None

        await asyncio.sleep(backoff_)

    async def backoff(self, backoff_: typing.Optional[float], /) -> None:
        """Sleep for the provided backoff or for the next exponent.

        This provides an alternative to iterating over this class.

        Parameters
        ----------
        backoff_ : typing.Optional[float]
            The time this should backoff for. If left as `builtins.None` then
            this will back off for the last time provided with
            `Backoff.set_next_backoff` if available or the next exponential time.
        """
        self._started = True
        if backoff_ is None and self._next_backoff is not None:
            backoff_ = self._next_backoff
            self._next_backoff = None

        elif backoff_ is None:
            backoff_ = next(self._backoff)

        await asyncio.sleep(backoff_)

    def finish(self) -> None:
        """Mark the iterator as finished to break out of the loop."""
        self._finished = True

    def reset(self) -> None:
        """Reset the backoff to it's original exponent to reuse it."""
        self._backoff.reset()
        self._finished = False
        self._next_backoff = None
        self._started = False

    def set_next_backoff(self, backoff_: float, /) -> None:
        """Specify a backoff time for the next iteration or `Backoff.backoff` call.

        If this is called then the exponent won't be increased for this iteration.

        !!! note
            Calling this multiple times in a single iteration will overwrite any
            previously set next backoff.
        """
        self._next_backoff = backoff_
