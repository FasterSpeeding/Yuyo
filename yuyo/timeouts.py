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
"""Classes used for handling timing out components and reaction handlers."""
from __future__ import annotations

__all__ = ["BasicTimeout", "NeverTimeout"]

import abc
import datetime
import typing


class AbstractTimeout(abc.ABC):
    """Abstract interface used to manage timing out a modal."""

    __slots__ = ()

    @property
    @abc.abstractmethod
    def has_expired(self) -> bool:
        """Whether this modal has timed-out."""

    @abc.abstractmethod
    def increment_uses(self) -> bool:
        """Add a use to the modal.

        Returns
        -------
        bool
            Whether the modal has now timed-out.
        """


class BasicTimeout(AbstractTimeout):
    """Basic modal timeout strategy.

    This implementation timeouts if `timeout` passes since the last call or
    when `max_uses` reaches `0`.
    """

    __slots__ = ("_last_triggered", "_timeout", "_uses_left")

    def __init__(self, timeout: typing.Union[datetime.timedelta, int, float], /, *, max_uses: int = 1) -> None:
        """Initialise a basic timeout.

        Parameters
        ----------
        timeout
            How long this modal should wait between calls before timing-out.
        max_uses
            The maximum amount of uses this modal allows.

            Setting this to `-1` marks it as unlimited.
        """
        if not isinstance(timeout, datetime.timedelta):
            timeout = datetime.timedelta(seconds=timeout)

        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        self._timeout = timeout
        self._uses_left = max_uses

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractTimeout>>.
        if self._uses_left == 0:
            return True

        return datetime.datetime.now(tz=datetime.timezone.utc) - self._last_triggered > self._timeout

    def increment_uses(self) -> bool:
        # <<inherited docstring from AbstractTimeout>>.
        if self._uses_left > 0:
            self._uses_left -= 1

        elif self._uses_left == 0:
            raise RuntimeError("Uses already depleted")

        self._last_triggered = datetime.datetime.now(tz=datetime.timezone.utc)
        return self._uses_left == 0


class NeverTimeout(AbstractTimeout):
    """Timeout implementation which never expires."""

    __slots__ = ()

    @property
    def has_expired(self) -> bool:
        # <<inherited docstring from AbstractTimeout>>.
        return False

    def increment_uses(self) -> bool:
        # <<inherited docstring from AbstractTimeout>>.
        return False
