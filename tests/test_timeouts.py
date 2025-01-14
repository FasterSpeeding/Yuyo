# BSD 3-Clause License
#
# Copyright (c) 2020-2025, Faster Speeding
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

import datetime

import freezegun
import pytest

from yuyo import timeouts


class TestSlidingTimeout:
    def test_has_expired(self) -> None:
        with freezegun.freeze_time() as frozen:
            timeout = timeouts.SlidingTimeout(datetime.timedelta(seconds=60), max_uses=4)

            for tick_time in [15, 15, 15, 14]:
                frozen.tick(datetime.timedelta(seconds=tick_time))
                assert timeout.has_expired is False

            frozen.tick(datetime.timedelta(seconds=2))
            assert timeout.has_expired is True

    def test_slides(self) -> None:
        with freezegun.freeze_time() as frozen:
            timeout = timeouts.SlidingTimeout(datetime.timedelta(seconds=30), max_uses=10)

            frozen.tick(datetime.timedelta(seconds=28))
            assert timeout.has_expired is False

            timeout.increment_uses()

            frozen.tick(datetime.timedelta(seconds=3))
            assert timeout.has_expired is False

            frozen.tick(datetime.timedelta(seconds=26))
            assert timeout.has_expired is False

            frozen.tick(datetime.timedelta(seconds=2))
            assert timeout.has_expired is True

    def test_has_expired_when_no_uses_left(self) -> None:
        timeout = timeouts.SlidingTimeout(datetime.timedelta(days=6000), max_uses=1)

        assert timeout.has_expired is False

        assert timeout.increment_uses() is True
        assert timeout.has_expired is True

    def test_increment_uses(self) -> None:
        timeout = timeouts.SlidingTimeout(datetime.timedelta(days=6000), max_uses=4)

        assert timeout.increment_uses() is False
        assert timeout.has_expired is False

        assert timeout.increment_uses() is False
        assert timeout.has_expired is False

        assert timeout.increment_uses() is False
        assert timeout.has_expired is False

        assert timeout.increment_uses() is True
        assert timeout.has_expired is True

    def test_increment_uses_when_unlimited(self) -> None:
        timeout = timeouts.SlidingTimeout(datetime.timedelta(days=6000), max_uses=-1)

        for _ in range(10000):
            assert timeout.increment_uses() is False
            assert timeout.has_expired is False

    def test_increment_uses_when_already_expired(self) -> None:
        timeout = timeouts.SlidingTimeout(datetime.timedelta(days=6000), max_uses=1)

        assert timeout.increment_uses() is True
        assert timeout.has_expired is True

        with pytest.raises(RuntimeError, match="Uses already depleted"):
            timeout.increment_uses()


class TestNeverTimeout:
    def test_has_expired(self) -> None:
        assert timeouts.NeverTimeout().has_expired is False

    def test_increment_uses(self) -> None:
        timeout = timeouts.NeverTimeout()

        for _ in range(10000):
            assert timeout.increment_uses() is False


def _now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.UTC)


class TestStaticTimeout:
    def test_has_expired(self) -> None:
        with freezegun.freeze_time() as frozen:
            timeout = timeouts.StaticTimeout(_now() + datetime.timedelta(seconds=60), max_uses=100)

            for _ in range(59):
                frozen.tick(datetime.timedelta(seconds=1))
                timeout.increment_uses()
                assert timeout.has_expired is False

            frozen.tick(datetime.timedelta(seconds=2))
            assert timeout.has_expired is True

    def test_has_expired_when_timezone_naive(self) -> None:
        with freezegun.freeze_time() as frozen:
            date = datetime.datetime.now()  # noqa: DTZ005
            timeout = timeouts.StaticTimeout(date + datetime.timedelta(seconds=60), max_uses=100)

            for _ in range(59):
                frozen.tick(datetime.timedelta(seconds=1))
                timeout.increment_uses()
                assert timeout.has_expired is False

            frozen.tick(datetime.timedelta(seconds=2))
            assert timeout.has_expired is True

    def test_has_expired_when_no_uses_left(self) -> None:
        timeout = timeouts.StaticTimeout(_now() + datetime.timedelta(days=60), max_uses=1)

        assert timeout.has_expired is False

        assert timeout.increment_uses() is True
        assert timeout.has_expired is True

    def test_increment_uses(self) -> None:
        timeout = timeouts.StaticTimeout(_now() + datetime.timedelta(days=6000), max_uses=4)

        assert timeout.increment_uses() is False
        assert timeout.has_expired is False

        assert timeout.increment_uses() is False
        assert timeout.has_expired is False

        assert timeout.increment_uses() is False
        assert timeout.has_expired is False

        assert timeout.increment_uses() is True
        assert timeout.has_expired is True

    def test_increment_uses_when_unlimited(self) -> None:
        timeout = timeouts.StaticTimeout(_now() + datetime.timedelta(days=40), max_uses=-1)

        for _ in range(10000):
            assert timeout.increment_uses() is False
            assert timeout.has_expired is False

    def test_increment_uses_when_already_expired(self) -> None:
        timeout = timeouts.StaticTimeout(_now() + datetime.timedelta(days=40000), max_uses=1)

        assert timeout.increment_uses() is True
        assert timeout.has_expired is True

        with pytest.raises(RuntimeError, match="Uses already depleted"):
            timeout.increment_uses()
