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

import datetime
from unittest import mock

import alluka
import freezegun
import hikari
import pytest

import yuyo

try:
    import tanjun

except ModuleNotFoundError:
    tanjun = None


class TestBaseContext:
    def test_id_match_property(self):
        context = yuyo.components.Context(
            mock.Mock(), mock.Mock(), "yeyeye meow meow", "", register_task=lambda v: None
        )

        assert context.id_match == "yeyeye meow meow"

    def test_id_metadata_property(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(), "", "very meta girl", register_task=lambda v: None)

        assert context.id_metadata == "very meta girl"

    @pytest.mark.parametrize(
        ("now", "expires_at"),
        [
            (
                datetime.datetime(2023, 3, 31, 20, 2, 15, 173495, tzinfo=datetime.timezone.utc),
                datetime.datetime(2023, 3, 31, 20, 17, 15, 173495, tzinfo=datetime.timezone.utc),
            ),
            (
                datetime.datetime(2019, 6, 2, 14, 6, 1, 432653, tzinfo=datetime.timezone.utc),
                datetime.datetime(2019, 6, 2, 14, 21, 1, 432653, tzinfo=datetime.timezone.utc),
            ),
        ],
    )
    def test_expires_at_property(self, now: datetime.datetime, expires_at: datetime.datetime):
        with freezegun.freeze_time(now):
            date = datetime.datetime.now(tz=datetime.timezone.utc)

            context = yuyo.components.Context(
                mock.Mock(), mock.Mock(created_at=date), "", "", register_task=lambda v: None
            )

            assert context.expires_at == expires_at

    def test_interaction_property(self):
        mock_interaction = mock.Mock()

        context = yuyo.components.Context(
            mock.Mock(), mock_interaction, "yeyeye meow meow", "", register_task=lambda v: None
        )

        assert context.interaction is mock_interaction


class TestComponentContext:
    def test_deprected_select_channels_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        with pytest.warns(DeprecationWarning):
            assert context.select_channels is mock_interaction.resolved.channels

    def test_deprecated_select_channels_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        with pytest.warns(DeprecationWarning):
            assert context.select_channels == {}

    def test_selected_channels_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        assert context.selected_channels is mock_interaction.resolved.channels

    def test_selected_channels_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        assert context.selected_channels == {}

    def test_deprecated_select_roles_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        with pytest.warns(DeprecationWarning):
            assert context.select_roles is mock_interaction.resolved.roles

    def test_deprecated_select_roles_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        with pytest.warns(DeprecationWarning):
            assert context.select_roles == {}

    def test_selected_roles_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        assert context.selected_roles is mock_interaction.resolved.roles

    def test_selected_roles_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        assert context.selected_roles == {}

    def test_deprecated_select_texts_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        with pytest.warns(DeprecationWarning):
            assert context.select_texts is mock_interaction.values

    def test_selected_texts_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        assert context.selected_texts is mock_interaction.values

    def test_deprecated_select_users_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        with pytest.warns(DeprecationWarning):
            assert context.select_users is mock_interaction.resolved.users

    def test_deprecated_select_users_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        with pytest.warns(DeprecationWarning):
            assert context.select_users == {}

    def test_selected_users_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        assert context.selected_users is mock_interaction.resolved.users

    def test_selected_users_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        assert context.selected_users == {}

    def test_deprecated_select_members_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        with pytest.warns(DeprecationWarning):
            assert context.select_members is mock_interaction.resolved.members

    def test_deprecated_select_members_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        with pytest.warns(DeprecationWarning):
            assert context.select_members == {}

    def test_selected_members_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        assert context.selected_members is mock_interaction.resolved.members

    def test_selected_members_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        assert context.selected_members == {}

    def test_client_property(self):
        mock_client = mock.Mock()
        context = yuyo.components.Context(mock_client, mock.Mock(), "", "", register_task=lambda v: None)

        assert context.client is mock_client


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

        with pytest.warns(DeprecationWarning):
            result = client.set_constant_id("123", mock_callback)  # pyright: ignore [ reportDeprecated ]

        assert result is client

        with pytest.warns(DeprecationWarning):
            assert client.get_constant_id("123") is mock_callback  # pyright: ignore [ reportDeprecated ]

    def test_set_constant_id_when_already_present_as_custom_id(self):
        mock_callback = mock.Mock()

        client = yuyo.ComponentClient()

        with pytest.warns(DeprecationWarning):
            client.set_constant_id("trans", mock_callback)  # pyright: ignore [ reportDeprecated ]

        with pytest.warns(DeprecationWarning), pytest.raises(
            ValueError, match="'trans' is already registered as a constant id"
        ):
            client.set_constant_id("trans", mock.Mock())  # pyright: ignore [ reportDeprecated ]

    def test_remove_constant_id(self):
        client = yuyo.ComponentClient()

        with pytest.warns(DeprecationWarning):
            client.set_constant_id("yuri", mock.Mock())  # pyright: ignore [ reportDeprecated ]

        with pytest.warns(DeprecationWarning):
            result = client.remove_constant_id("yuri")  # pyright: ignore [ reportDeprecated ]

        assert result is client

        with pytest.warns(DeprecationWarning):
            assert client.get_constant_id("yuri") is None  # pyright: ignore [ reportDeprecated ]

    def test_remove_constant_id_when_not_present(self):
        with pytest.warns(DeprecationWarning):
            client = (
                yuyo.ComponentClient()
                .set_constant_id("e", mock.Mock())  # pyright: ignore [ reportDeprecated ]
                .set_constant_id("h", mock.Mock())  # pyright: ignore [ reportDeprecated ]
            )

        with pytest.warns(DeprecationWarning), pytest.raises(KeyError):
            client.remove_constant_id("yuri")  # pyright: ignore [ reportDeprecated ]

    def test_with_constant_id(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient()

        with pytest.warns(DeprecationWarning):
            result = client.with_constant_id("yuri")(mock_callback)  # pyright: ignore [ reportDeprecated ]

        assert result is mock_callback

        with pytest.warns(DeprecationWarning):
            assert client.get_constant_id("yuri") is mock_callback  # pyright: ignore [ reportDeprecated ]

    def test_with_constant_id_when_already_present_as_custom_id(self):
        mock_callback = mock.Mock()
        client = yuyo.ComponentClient()

        with pytest.warns(DeprecationWarning):
            client.set_constant_id("trans", mock_callback)  # pyright: ignore [ reportDeprecated ]

        with pytest.warns(DeprecationWarning), pytest.raises(
            ValueError, match="'trans' is already registered as a constant id"
        ):
            client.with_constant_id("trans")(mock.Mock())  # pyright: ignore [ reportDeprecated ]

    def test_set_executor(self):
        mock_executor = mock.Mock(timeout=None)
        client = yuyo.ComponentClient()

        with pytest.warns(DeprecationWarning):
            result = client.set_executor(555555, mock_executor)  # pyright: ignore [ reportDeprecated ]

        assert result is client

        with pytest.warns(DeprecationWarning):
            assert client.get_executor(555555) is mock_executor  # pyright: ignore [ reportDeprecated ]

    def test_set_executor_when_timeout_set(self):
        mock_executor = mock.Mock(timeout=123)
        client = yuyo.ComponentClient()

        with pytest.warns(DeprecationWarning):
            result = client.set_executor(555555, mock_executor)  # pyright: ignore [ reportDeprecated ]

        assert result is client

        with pytest.warns(DeprecationWarning):
            assert client.get_executor(555555) is mock_executor  # pyright: ignore [ reportDeprecated ]

    def test_remove_executor(self):
        client = yuyo.ComponentClient()

        with pytest.warns(DeprecationWarning):
            client.set_executor(555555, mock.Mock(timeout=None))  # pyright: ignore [ reportDeprecated ]

        with pytest.warns(DeprecationWarning):
            result = client.remove_executor(555555)  # pyright: ignore [ reportDeprecated ]

        assert result is client

        with pytest.warns(DeprecationWarning):
            assert client.get_executor(555555) is None  # pyright: ignore [ reportDeprecated ]


class TestSingleExecutor:
    def test_custom_ids_property(self):
        executor = yuyo.components.SingleExecutor("dkkpoeewlk", mock.Mock())

        assert executor.custom_ids == ["dkkpoeewlk"]

    @pytest.mark.asyncio()
    async def test_execute(self):
        mock_callback = mock.AsyncMock()
        client = yuyo.components.Client()
        ctx = yuyo.components.ComponentContext(client, mock.Mock(), "", "", lambda _: None)
        executor = yuyo.components.SingleExecutor("dkkpoeewlk", mock_callback.__call__, ephemeral_default=True)

        await executor.execute(ctx)

        assert ctx._ephemeral_default is True
        mock_callback.assert_awaited_once_with(ctx)


def test_as_single_executor():
    mock_callback = mock.Mock()

    result = yuyo.components.as_single_executor("yeet", ephemeral_default=True)(mock_callback)

    assert isinstance(result, yuyo.components.SingleExecutor)

    assert result.custom_ids == ["yeet"]
    assert result._callback is mock_callback
    assert result._ephemeral_default is True


class TestComponentExecutor:
    ...


class TestActionRowExecutor:
    def test_add_select_menu(self):
        mock_callback = mock.Mock()

        row = yuyo.components.ActionRowExecutor().add_select_menu(
            hikari.ComponentType.ROLE_SELECT_MENU,
            mock_callback,
            custom_id="custom",
            placeholder="place",
            min_values=4,
            max_values=7,
            is_disabled=True,
        )

        assert row.callbacks["custom"] is mock_callback

        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.ROLE_SELECT_MENU
        assert component.custom_id == "custom"
        assert component.placeholder == "place"
        assert component.min_values == 4
        assert component.max_values == 7
        assert component.is_disabled is True

    def test_add_select_menu_with_defaults(self):
        mock_callback = mock.Mock()

        row = yuyo.components.ActionRowExecutor().add_select_menu(hikari.ComponentType.ROLE_SELECT_MENU, mock_callback)

        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.ROLE_SELECT_MENU
        assert isinstance(component.custom_id, str)
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1
        assert component.is_disabled is False

        assert row.callbacks[component.custom_id] is mock_callback

    def test_add_select_menu_with_deprecated_order(self):
        mock_callback = mock.Mock()
        row = yuyo.components.ActionRowExecutor()

        with pytest.warns(DeprecationWarning):
            row.add_select_menu(  # pyright: ignore [ reportDeprecated ]
                mock_callback, hikari.ComponentType.ROLE_SELECT_MENU, custom_id="meow meow"
            )

        assert row.callbacks["meow meow"] is mock_callback

        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.ROLE_SELECT_MENU
        assert component.custom_id == "meow meow"

    def test_text_menu_builder_uses_option_count_when_max_values_too_high(self):
        action_row = yuyo.components.ActionRowExecutor()

        (
            action_row.add_text_menu(mock.AsyncMock(), max_values=20)
            .add_option("meow", "blah")
            .add_option("arrest", "me")
            .add_option("with", "your")
            .add_option("sweet", "lullaby")
        )

        assert action_row.build()["components"][0]["max_values"] == 4

    def test_text_menu_builder_uses_max_values_when_enough_options(self):
        action_row = yuyo.components.ActionRowExecutor()

        (
            action_row.add_text_menu(mock.AsyncMock(), max_values=3)
            .add_option("meow", "blah")
            .add_option("arrest", "me")
            .add_option("with", "your")
            .add_option("sweet", "lullaby")
            .add_option("get up", "get up")
        )

        assert action_row.build()["components"][0]["max_values"] == 3


class TestActionColumnExecutor:
    def test_add_select_menu(self):
        mock_callback = mock.Mock()

        column = yuyo.components.ActionColumnExecutor().add_select_menu(
            hikari.ComponentType.USER_SELECT_MENU,
            mock_callback,
            custom_id="meowed",
            placeholder="heins",
            min_values=8,
            max_values=12,
            is_disabled=True,
        )

        assert column._callbacks["meowed"] is mock_callback

        assert len(column.rows) == 1
        assert len(column.rows[0].components) == 1
        component = column.rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert component.custom_id == "meowed"
        assert component.placeholder == "heins"
        assert component.min_values == 8
        assert component.max_values == 12
        assert component.is_disabled is True

    def test_add_select_menu_with_defaults(self):
        mock_callback = mock.Mock()

        column = yuyo.components.ActionColumnExecutor().add_select_menu(
            hikari.ComponentType.USER_SELECT_MENU, mock_callback
        )

        assert len(column.rows) == 1
        assert len(column.rows[0].components) == 1
        component = column.rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert isinstance(component.custom_id, str)
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1
        assert component.is_disabled is False

        assert column._callbacks[component.custom_id] is mock_callback

    def test_add_select_menu_with_deprecated_order(self):
        mock_callback = mock.Mock()
        column = yuyo.components.ActionColumnExecutor()

        with pytest.warns(DeprecationWarning):
            column.add_select_menu(  # pyright: ignore [ reportDeprecated ]
                mock_callback, hikari.ComponentType.USER_SELECT_MENU, custom_id="meow meowy"
            )

        assert column._callbacks["meow meowy"] is mock_callback

        assert len(column.rows) == 1
        assert len(column.rows[0].components) == 1
        component = column.rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert component.custom_id == "meow meowy"

    def test_add_static_select_menu(self):
        class Column(yuyo.components.ActionColumnExecutor):
            ...

        mock_callback = mock.Mock()

        column = Column.add_static_select_menu(
            hikari.ComponentType.USER_SELECT_MENU,
            mock_callback,
            custom_id="eep",
            placeholder="peep",
            min_values=9,
            max_values=11,
            is_disabled=True,
        )()

        assert column._callbacks["eep"] is mock_callback

        assert len(column.rows) == 1
        assert len(column.rows[0].components) == 1
        component = column.rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert component.custom_id == "eep"
        assert component.placeholder == "peep"
        assert component.min_values == 9
        assert component.max_values == 11
        assert component.is_disabled is True

    def test_add_static_select_menu_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            ...

        mock_callback = mock.Mock()

        column = Column.add_static_select_menu(hikari.ComponentType.USER_SELECT_MENU, mock_callback)()

        assert len(column.rows) == 1
        assert len(column.rows[0].components) == 1
        component = column.rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert isinstance(component.custom_id, str)
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1
        assert component.is_disabled is False

        assert column._callbacks[component.custom_id] is mock_callback

    def test_add_static_select_menu_with_deprecated_order(self):
        class Column(yuyo.components.ActionColumnExecutor):
            ...

        mock_callback = mock.Mock()

        with pytest.warns(DeprecationWarning):
            Column.add_static_select_menu(  # pyright: ignore [ reportDeprecated ]
                mock_callback, hikari.ComponentType.MENTIONABLE_SELECT_MENU, custom_id="meowy"
            )

        column = Column()

        assert column._callbacks["meowy"] is mock_callback

        assert len(column.rows) == 1
        assert len(column.rows[0].components) == 1
        component = column.rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.MENTIONABLE_SELECT_MENU
        assert component.custom_id == "meowy"

    def test_with_interactive_button_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_interactive_button(
                hikari.ButtonStyle.DANGER, label="nyaa", emoji="eeper", is_disabled=True, custom_id="meow"
            )
            async def on_botton(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.custom_id == "meow"
        assert component.style is hikari.ButtonStyle.DANGER
        assert component.emoji == "eeper"
        assert component.label == "nyaa"
        assert component.is_disabled is True

    def test_with_interactive_button_descriptor_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY)
            async def on_botton(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.style is hikari.ButtonStyle.PRIMARY
        assert component.emoji is hikari.UNDEFINED
        assert component.label is hikari.UNDEFINED
        assert component.is_disabled is False

    def test_with_link_button_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            link_button = yuyo.components.link_button("https://example.com", label="x", emoji="y", is_disabled=True)

        Column()

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.style is hikari.ButtonStyle.LINK
        assert component.url == "https://example.com"
        assert component.emoji == "y"
        assert component.label == "x"
        assert component.is_disabled is True

    def test_with_link_button_descriptor_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            link_button = yuyo.components.link_button("https://example.com/eepers")

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.url == "https://example.com/eepers"
        assert component.style is hikari.ButtonStyle.LINK
        assert component.emoji is hikari.UNDEFINED
        assert component.label is hikari.UNDEFINED
        assert component.is_disabled is False

    def test_with_select_menu_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_select_menu(
                hikari.ComponentType.USER_SELECT_MENU,
                custom_id="cust",
                is_disabled=True,
                placeholder="place me",
                min_values=3,
                max_values=12,
            )
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.custom_id == "cust"
        assert component.is_disabled is True
        assert component.placeholder == "place me"
        assert component.min_values == 3
        assert component.max_values == 12

    def test_with_select_menu_descriptor_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_select_menu(hikari.ComponentType.USER_SELECT_MENU)
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.is_disabled is False
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1

    def test_with_channel_menu_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_channel_menu(
                channel_types=[hikari.PrivateChannel, hikari.ChannelType.GUILD_NEWS],
                is_disabled=True,
                placeholder="me",
                min_values=2,
                max_values=5,
            )
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.ChannelSelectMenuBuilder)
        assert component.channel_types == [
            hikari.ChannelType.DM,
            hikari.ChannelType.GROUP_DM,
            hikari.ChannelType.GUILD_NEWS,
        ]
        assert component.is_disabled is True
        assert component.placeholder == "me"
        assert component.min_values == 2
        assert component.max_values == 5

    def test_with_channel_menu_descriptor_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_channel_menu
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.ChannelSelectMenuBuilder)
        assert component.channel_types == []
        assert component.is_disabled is False
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1

    def test_with_text_menu_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_text_menu(
                options=[
                    hikari.impl.SelectOptionBuilder(label="echo", value="zulu"),
                    hikari.impl.SelectOptionBuilder(
                        label="label", value="but", description="echo", emoji="a", is_default=True
                    ),
                ],
                is_disabled=True,
                placeholder="hello there",
                min_values=11,
                max_values=15,
            )
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.TextSelectMenuBuilder)
        assert component.options == [
            hikari.impl.SelectOptionBuilder(label="echo", value="zulu"),
            hikari.impl.SelectOptionBuilder(label="label", value="but", description="echo", emoji="a", is_default=True),
        ]
        assert component.is_disabled is True
        assert component.placeholder == "hello there"
        assert component.min_values == 11
        assert component.max_values == 15

    def test_with_text_menu_descriptor_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.with_option("lab", "man", description="last", emoji=123321, is_default=False)
            @yuyo.components.with_option("label", "value")
            @yuyo.components.with_option("aaa", "bbb", description="descript", emoji="em", is_default=True)
            @yuyo.components.as_text_menu
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.TextSelectMenuBuilder)
        assert component.options == [
            hikari.impl.SelectOptionBuilder(
                label="aaa", value="bbb", description="descript", emoji="em", is_default=True
            ),
            hikari.impl.SelectOptionBuilder(label="label", value="value"),
            hikari.impl.SelectOptionBuilder(
                label="lab", value="man", description="last", emoji=123321, is_default=False
            ),
        ]
        assert component.is_disabled is False
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1


def test_with_static_select_menu():
    mock_callback = mock.Mock()

    @yuyo.components.with_static_select_menu(
        hikari.ComponentType.USER_SELECT_MENU,
        mock_callback,
        custom_id="aaa",
        placeholder="bbb",
        min_values=5,
        max_values=23,
        is_disabled=True,
    )
    class Column(yuyo.components.ActionColumnExecutor):
        ...

    column = Column()

    assert column._callbacks["aaa"] is mock_callback

    assert len(column.rows) == 1
    assert len(column.rows[0].components) == 1

    component = column.rows[0].components[0]
    assert isinstance(component, hikari.api.SelectMenuBuilder)
    assert component.type is hikari.ComponentType.USER_SELECT_MENU
    assert component.custom_id == "aaa"
    assert component.placeholder == "bbb"
    assert component.min_values == 5
    assert component.max_values == 23
    assert component.is_disabled is True


def test_with_static_select_menu_with_defaults():
    mock_callback = mock.Mock()

    @yuyo.components.with_static_select_menu(hikari.ComponentType.USER_SELECT_MENU, mock_callback)
    class Column(yuyo.components.ActionColumnExecutor):
        ...

    column = Column()

    assert len(column.rows) == 1
    assert len(column.rows[0].components) == 1

    component = column.rows[0].components[0]
    assert isinstance(component, hikari.api.SelectMenuBuilder)
    assert component.type is hikari.ComponentType.USER_SELECT_MENU
    assert isinstance(component.custom_id, str)
    assert component.placeholder is hikari.UNDEFINED
    assert component.min_values == 0
    assert component.max_values == 1
    assert component.is_disabled is False

    assert column._callbacks[component.custom_id] is mock_callback


def test_with_static_select_menu_with_deprecated_order():
    class Column(yuyo.components.ActionColumnExecutor):
        ...

    mock_callback = mock.Mock()

    with pytest.warns(DeprecationWarning):
        yuyo.components.with_static_select_menu(  # pyright: ignore [ reportDeprecated ]
            mock_callback, hikari.ComponentType.USER_SELECT_MENU, custom_id="meowers"
        )(Column)

    column = Column()

    assert column._callbacks["meowers"] is mock_callback

    assert len(column.rows) == 1
    assert len(column.rows[0].components) == 1

    component = column.rows[0].components[0]
    assert isinstance(component, hikari.api.SelectMenuBuilder)
    assert component.type is hikari.ComponentType.USER_SELECT_MENU
    assert component.custom_id == "meowers"
