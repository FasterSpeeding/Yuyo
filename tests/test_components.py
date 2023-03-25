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

# pyright: reportPrivateUsage=none
# pyright: reportUnknownMemberType=none
# This leads to too many false-positives around mocks.

from unittest import mock

import alluka
import hikari
import pytest

import yuyo

try:
    import tanjun

except ModuleNotFoundError:
    tanjun = None


class TestBaseContext:
    ...


class TestComponentContext:
    def test_select_channels_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), interaction=mock_interaction, register_task=lambda v: None)

        assert context.select_channels is mock_interaction.resolved.channels

    def test_select_channels_property_when_no_resolved(self):
        context = yuyo.components.Context(
            mock.Mock(), interaction=mock.Mock(resolved=None), register_task=lambda v: None
        )

        assert context.select_channels == {}

    def test_select_roles_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), interaction=mock_interaction, register_task=lambda v: None)

        assert context.select_roles is mock_interaction.resolved.roles

    def test_select_roles_property_when_no_resolved(self):
        context = yuyo.components.Context(
            mock.Mock(), interaction=mock.Mock(resolved=None), register_task=lambda v: None
        )

        assert context.select_roles == {}

    def test_select_texts_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), interaction=mock_interaction, register_task=lambda v: None)

        assert context.select_texts is mock_interaction.values

    def test_select_users_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), interaction=mock_interaction, register_task=lambda v: None)

        assert context.select_users is mock_interaction.resolved.users

    def test_select_users_property_when_no_resolved(self):
        context = yuyo.components.Context(
            mock.Mock(), interaction=mock.Mock(resolved=None), register_task=lambda v: None
        )

        assert context.select_users == {}

    def test_select_members_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), interaction=mock_interaction, register_task=lambda v: None)

        assert context.select_members is mock_interaction.resolved.members

    def test_select_members_property_when_no_resolved(self):
        context = yuyo.components.Context(
            mock.Mock(), interaction=mock.Mock(resolved=None), register_task=lambda v: None
        )

        assert context.select_members == {}


class TestComponentClient:
    def test___init___when_event_managed(self):
        mock_event_manger = mock.Mock()

        client = yuyo.ComponentClient(event_manager=mock_event_manger, event_managed=True)

        mock_event_manger.subscribe.assert_has_calls(
            [mock.call(hikari.StartingEvent, client._on_starting), mock.call(hikari.StoppingEvent, client._on_stopping)]
        )

    def test___init___when_event_managed_is_none_but_event_manager_passed(self):
        mock_event_manger = mock.Mock()

        client = yuyo.ComponentClient(event_manager=mock_event_manger, event_managed=None)

        mock_event_manger.subscribe.assert_has_calls(
            [mock.call(hikari.StartingEvent, client._on_starting), mock.call(hikari.StoppingEvent, client._on_stopping)]
        )

    def test_alluka(self):
        client = yuyo.ComponentClient(event_manager=mock.Mock())

        assert isinstance(client.alluka, alluka.Client)
        assert client.alluka.get_type_dependency(yuyo.ComponentClient) is client

    def test_alluka_with_passed_through_client(self):
        mock_alluka = mock.Mock()

        client = yuyo.ComponentClient(alluka=mock_alluka, event_manager=mock.Mock())

        assert client.alluka is mock_alluka
        mock_alluka.set_type_dependency.assert_not_called()

    def test_from_gateway_bot(self):
        mock_bot = mock.Mock()
        mock_init = mock.Mock(return_value=None)

        class StubClient(yuyo.ComponentClient):
            __init__ = mock_init

        stub_client = StubClient.from_gateway_bot(mock_bot)

        assert isinstance(stub_client, StubClient)
        mock_init.assert_called_once_with(alluka=None, event_manager=mock_bot.event_manager, event_managed=True)

    def test_from_gateway_bot_with_optional_kwargs(self):
        mock_alluka = mock.Mock()
        mock_bot = mock.Mock()
        mock_init = mock.Mock(return_value=None)

        class StubClient(yuyo.ComponentClient):
            __init__ = mock_init

        stub_client = StubClient.from_gateway_bot(mock_bot, alluka=mock_alluka, event_managed=False)

        assert isinstance(stub_client, StubClient)
        mock_init.assert_called_once_with(alluka=mock_alluka, event_manager=mock_bot.event_manager, event_managed=False)

    def test_from_rest_bot(self):
        mock_bot = mock.Mock()
        mock_init = mock.Mock(return_value=None)

        class StubClient(yuyo.ComponentClient):
            __init__ = mock_init

        stub_client = StubClient.from_rest_bot(mock_bot)

        assert isinstance(stub_client, StubClient)
        mock_init.assert_called_once_with(alluka=None, server=mock_bot.interaction_server)
        mock_bot.add_shutdown_callback.assert_not_called()
        mock_bot.add_startup_callback.assert_not_called()

    def test_from_rest_bot_with_optional_kwargs(self):
        mock_alluka = mock.Mock()
        mock_bot = mock.Mock()
        mock_init = mock.Mock(return_value=None)

        class StubClient(yuyo.ComponentClient):
            __init__ = mock_init

        stub_client = StubClient.from_rest_bot(mock_bot, alluka=mock_alluka, bot_managed=True)

        assert isinstance(stub_client, StubClient)
        mock_init.assert_called_once_with(alluka=mock_alluka, server=mock_bot.interaction_server)
        mock_bot.add_shutdown_callback.assert_called_once_with(stub_client._on_stopping)
        mock_bot.add_startup_callback.assert_called_once_with(stub_client._on_starting)

    @pytest.mark.skipif(tanjun is None, reason="Tanjun specific test")
    def test_from_tanjun(self):
        assert tanjun

        mock_bot = mock.Mock()
        mock_init = mock.Mock(return_value=None)

        class StubClient(yuyo.ComponentClient):
            __init__ = mock_init

        stub_client = StubClient.from_tanjun(mock_bot)

        assert isinstance(stub_client, StubClient)
        mock_init.assert_called_once_with(
            alluka=mock_bot.injector, event_manager=mock_bot.events, server=mock_bot.server
        )
        mock_bot.injector.set_type_dependency.assert_called_once_with(yuyo.ComponentClient, stub_client)
        mock_bot.add_client_callback.assert_has_calls(
            [
                mock.call(tanjun.ClientCallbackNames.STARTING, stub_client.open),
                mock.call(tanjun.ClientCallbackNames.CLOSING, stub_client.close),
            ]
        )

    @pytest.mark.skipif(tanjun is None, reason="Tanjun specific test")
    def test_from_tanjun_when_not_tanjun_managed(self):
        assert tanjun

        mock_bot = mock.Mock()
        mock_init = mock.Mock(return_value=None)

        class StubClient(yuyo.ComponentClient):
            __init__ = mock_init

        stub_client = StubClient.from_tanjun(mock_bot, tanjun_managed=False)

        assert isinstance(stub_client, StubClient)
        mock_init.assert_called_once_with(
            alluka=mock_bot.injector, event_manager=mock_bot.events, server=mock_bot.server
        )
        mock_bot.injector.set_type_dependency.assert_called_once_with(yuyo.ComponentClient, stub_client)
        mock_bot.add_client_callback.assert_not_called()

    @pytest.mark.asyncio()
    async def test__on_starting(self):
        mock_open = mock.Mock()

        class StubClient(yuyo.ComponentClient):
            open = mock_open  # noqa: VNE003

        stub_client = StubClient()

        await stub_client._on_starting(mock.Mock())

        mock_open.assert_called_once_with()

    @pytest.mark.asyncio()
    async def test__on_stopping(self):
        mock_close = mock.Mock()

        class StubClient(yuyo.ComponentClient):
            close = mock_close

        stub_client = StubClient()

        await stub_client._on_stopping(mock.Mock())

        mock_close.assert_called_once_with()

    @pytest.mark.skip(reason="Not implemented yet")
    @pytest.mark.asyncio()
    async def test__gc(self):
        ...

    @pytest.mark.skip(reason="Not implemented yet")
    def test_close(self):
        ...

    @pytest.mark.skip(reason="Not implemented yet")
    def test_open(self):
        ...

    @pytest.mark.skip(reason="Not implemented yet")
    @pytest.mark.asyncio()
    async def test_on_gateway_event(self):
        ...

    @pytest.mark.skip(reason="Not implemented yet")
    @pytest.mark.asyncio()
    async def test_on_rest_request(self):
        ...

    def test_set_constant_id(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient()

        result = client.set_constant_id("123", mock_callback)

        assert result is client
        assert client.get_constant_id("123") is mock_callback
        assert client._constant_ids["123"] is mock_callback
        assert "123" not in client._prefix_ids

    def test_set_constant_id_when_already_present_as_custom_id(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient().set_constant_id("trans", mock_callback)

        with pytest.raises(ValueError, match="'trans' is already registered as a constant id"):
            client.set_constant_id("trans", mock.Mock())

        assert client.get_constant_id("trans") is mock_callback
        assert client._constant_ids["trans"] is mock_callback
        assert "trans" not in client._prefix_ids

    def test_set_constant_id_when_already_present_as_prefix_id(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient().set_constant_id("trans2", mock_callback, prefix_match=True)

        with pytest.raises(ValueError, match="'trans2' is already registered as a prefix match"):
            client.set_constant_id("trans2", mock.Mock())

        assert client.get_constant_id("trans2") is mock_callback
        assert "trans2" not in client._constant_ids
        assert client._prefix_ids["trans2"] is mock_callback

    def test_set_constant_id_when_prefix_match(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient()

        result = client.set_constant_id("456", mock_callback, prefix_match=True)

        assert result is client
        assert client.get_constant_id("456") is mock_callback
        assert "456" not in client._constant_ids
        assert client._prefix_ids["456"] is mock_callback

    def test_remove_constant_id(self):
        client = yuyo.ComponentClient().set_constant_id("yuri", mock.Mock())

        result = client.remove_constant_id("yuri")

        assert result is client
        assert client.get_constant_id("yuri") is None
        assert "yuri" not in client._constant_ids
        assert "yuri" not in client._prefix_ids

    def test_remove_constant_id_for_prefix_id(self):
        client = yuyo.ComponentClient().set_constant_id("yuro", mock.Mock(), prefix_match=True)

        result = client.remove_constant_id("yuro")

        assert result is client
        assert client.get_constant_id("yuro") is None
        assert "yuro" not in client._constant_ids
        assert "yuro" not in client._prefix_ids

    def test_remove_constant_id_when_not_present(self):
        client = (
            yuyo.ComponentClient()
            .set_constant_id("e", mock.Mock())
            .set_constant_id("h", mock.Mock(), prefix_match=True)
        )

        with pytest.raises(KeyError):
            client.remove_constant_id("yuri")

        assert "e" in client._constant_ids
        assert "h" in client._prefix_ids

    def test_with_constant_id(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient()

        result = client.with_constant_id("yuri")(mock_callback)

        assert result is mock_callback
        assert client._constant_ids["yuri"] is mock_callback
        assert "yuri" not in client._prefix_ids

    def test_with_constant_id_when_prefix_match(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient()

        result = client.with_constant_id("yuru", prefix_match=True)(mock_callback)

        assert result is mock_callback
        assert "yuru" not in client._constant_ids
        assert client._prefix_ids["yuru"] is mock_callback

    def test_with_constant_id_when_already_present_as_custom_id(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient().set_constant_id("trans", mock_callback)

        with pytest.raises(ValueError, match="'trans' is already registered as a constant id"):
            client.with_constant_id("trans")(mock.Mock())

        assert client.get_constant_id("trans") is mock_callback
        assert client._constant_ids["trans"] is mock_callback
        assert "trans" not in client._prefix_ids

    def test_with_constant_id_when_already_present_as_prefix_id(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient().set_constant_id("trans2", mock_callback, prefix_match=True)

        with pytest.raises(ValueError, match="'trans2' is already registered as a prefix match"):
            client.with_constant_id("trans2")(mock.Mock())

        assert client.get_constant_id("trans2") is mock_callback
        assert "trans2" not in client._constant_ids
        assert client._prefix_ids["trans2"] is mock_callback

    def test_set_executor(self):
        mock_executor = mock.Mock()
        client = yuyo.ComponentClient()

        result = client.set_executor(555555, mock_executor)

        assert result is client
        assert client.get_executor(555555) is mock_executor

    def test_remove_executor(self):
        client = yuyo.ComponentClient().set_executor(555555, mock.Mock())

        result = client.remove_executor(555555)

        assert result is client
        assert client.get_executor(555555) is None


class TestActionRowExecutor:
    def test_text_select_builder_uses_option_count_when_max_values_too_high(self):
        action_row = yuyo.components.ActionRowExecutor()

        (
            action_row.add_text_select(mock.AsyncMock(), max_values=20)
            .add_option("meow", "blah")
            .add_to_menu()
            .add_option("arrest", "me")
            .add_to_menu()
            .add_option("with", "your")
            .add_to_menu()
            .add_option("sweet", "lullaby")
            .add_to_menu()
        )

        assert action_row.build()["components"][0]["max_values"] == 4

    def test_text_select_builder_uses_max_values_when_enough_options(self):
        action_row = yuyo.components.ActionRowExecutor()

        (
            action_row.add_text_select(mock.AsyncMock(), max_values=3)
            .add_option("meow", "blah")
            .add_to_menu()
            .add_option("arrest", "me")
            .add_to_menu()
            .add_option("with", "your")
            .add_to_menu()
            .add_option("sweet", "lullaby")
            .add_to_menu()
            .add_option("get up", "get up")
            .add_to_menu()
        )

        assert action_row.build()["components"][0]["max_values"] == 3
