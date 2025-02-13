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

# pyright: reportUnknownMemberType=none
# This leads to too many false-positives around mocks.

from unittest import mock

import alluka
import alluka.local

from yuyo import reactions


class TestReactionClient:
    def test_alluka(self) -> None:
        client = reactions.ReactionClient(rest=mock.AsyncMock(), event_manager=mock.Mock())

        assert isinstance(client.alluka, alluka.Client)
        assert client.alluka.get_type_dependency(reactions.ReactionClient) is client

    def test_alluka_when_alluka_local_client(self) -> None:
        with alluka.local.scope_client() as expected_alluka_client:
            client = reactions.ReactionClient(rest=mock.AsyncMock(), event_manager=mock.Mock())

            assert client.alluka is expected_alluka_client

    def test_alluka_with_passed_through_client(self) -> None:
        mock_alluka = mock.Mock()

        client = reactions.ReactionClient(alluka=mock_alluka, rest=mock.AsyncMock(), event_manager=mock.Mock())

        assert client.alluka is mock_alluka
        mock_alluka.set_type_dependency.assert_not_called()


class TestReactionHandler:
    def test_authors_property(self) -> None:
        handler = reactions.ReactionHandler(authors=[123, 321, 543, 1234])

        assert handler.authors == {123, 321, 543, 1234}
