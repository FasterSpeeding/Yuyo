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
import inspect
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
    def test_selected_channels_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        assert context.selected_channels is mock_interaction.resolved.channels

    def test_selected_channels_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        assert context.selected_channels == {}

    def test_selected_roles_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        assert context.selected_roles is mock_interaction.resolved.roles

    def test_selected_roles_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        assert context.selected_roles == {}

    def test_selected_texts_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        assert context.selected_texts is mock_interaction.values

    def test_selected_users_property(self):
        mock_interaction = mock.Mock()
        context = yuyo.components.Context(mock.Mock(), mock_interaction, "", "", register_task=lambda v: None)

        assert context.selected_users is mock_interaction.resolved.users

    def test_selected_users_property_when_no_resolved(self):
        context = yuyo.components.Context(mock.Mock(), mock.Mock(resolved=None), "", "", register_task=lambda v: None)

        assert context.selected_users == {}

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


class TestActionColumnExecutor:
    def test_init_id_metadata_handling(self):
        class Column(yuyo.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, custom_id="Custme")
            async def meowers(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_user_menu
            async def men(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_role_menu
            async def role_me(self, ctx: yuyo.components.Context) -> None:
                ...

        column = Column(id_metadata={"role_me": "meowers", "Custme": "nyann"})

        assert len(column.rows) == 3

        assert len(column.rows[0].components) == 1
        component = column.rows[0].components[0]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.custom_id == "Custme:nyann"

        assert len(column.rows[1].components) == 1
        component = column.rows[1].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.custom_id == "gm&uKe557h"

        assert len(column.rows[2].components) == 1
        component = column.rows[2].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.custom_id == "$qY^N`e%|!:meowers"

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

    def test_add_static_select_menu(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

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
            __slots__ = ()

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
        assert component.custom_id == "o+i~>X~tPH"
        assert component.style is hikari.ButtonStyle.PRIMARY
        assert component.emoji is hikari.UNDEFINED
        assert component.label is hikari.UNDEFINED
        assert component.is_disabled is False

    @pytest.mark.asyncio()
    async def test_with_interactive_button_descriptor_when_called_as_a_method(self):
        mock_callback = mock.AsyncMock()
        mock_ctx = mock.Mock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY)
            async def on_botton(self, ctx: yuyo.components.ComponentContext) -> None:
                await mock_callback(self, ctx)

        column = Column()

        await column.on_botton(mock_ctx)

        mock_callback.assert_awaited_once_with(column, mock_ctx)

    @pytest.mark.asyncio()
    async def test_with_interactive_button_descriptor_when_accessed_on_class(self):
        mock_callback = mock.AsyncMock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            on_botton = yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY)(mock_callback)

        assert Column.on_botton is mock_callback

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

    def test_with_mentionable_menu_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_mentionable_menu(
                custom_id="cust", is_disabled=True, placeholder="place me", min_values=3, max_values=12
            )
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.MENTIONABLE_SELECT_MENU
        assert component.custom_id == "cust"
        assert component.is_disabled is True
        assert component.placeholder == "place me"
        assert component.min_values == 3
        assert component.max_values == 12

    def test_with_mentionable_menu_descriptor_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_mentionable_menu
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.MENTIONABLE_SELECT_MENU
        assert component.custom_id == "g%mwOz4?MG"
        assert component.is_disabled is False
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1

    @pytest.mark.asyncio()
    async def test_with_mentionable_menu_descriptor_when_called_as_a_method(self):
        mock_callback = mock.AsyncMock()
        mock_ctx = mock.Mock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_mentionable_menu
            async def on_mentionable_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                await mock_callback(self, ctx)

        column = Column()

        await column.on_mentionable_menu(mock_ctx)

        mock_callback.assert_awaited_once_with(column, mock_ctx)

    @pytest.mark.asyncio()
    async def test_with_mentionable_menu_descriptor_when_accessed_on_class(self):
        mock_callback = mock.AsyncMock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            on_mentionable_menu = yuyo.components.as_mentionable_menu(mock_callback)

        assert Column.on_mentionable_menu is mock_callback

    def test_with_role_menu_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_role_menu(
                custom_id="cust", is_disabled=True, placeholder="place me", min_values=3, max_values=12
            )
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.ROLE_SELECT_MENU
        assert component.custom_id == "cust"
        assert component.is_disabled is True
        assert component.placeholder == "place me"
        assert component.min_values == 3
        assert component.max_values == 12

    def test_with_role_menu_descriptor_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_role_menu
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.ROLE_SELECT_MENU
        assert component.custom_id == "0+0h|zG?E-"
        assert component.is_disabled is False
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1

    @pytest.mark.asyncio()
    async def test_with_role_menu_descriptor_when_called_as_a_method(self):
        mock_callback = mock.AsyncMock()
        mock_ctx = mock.Mock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_role_menu
            async def on_role_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                await mock_callback(self, ctx)

        column = Column()

        await column.on_role_menu(mock_ctx)

        mock_callback.assert_awaited_once_with(column, mock_ctx)

    @pytest.mark.asyncio()
    async def test_with_role_menu_descriptor_when_accessed_on_class(self):
        mock_callback = mock.AsyncMock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            on_role_menu = yuyo.components.as_role_menu(mock_callback)

        assert Column.on_role_menu is mock_callback

    def test_with_user_menu_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_user_menu(
                custom_id="cust", is_disabled=True, placeholder="place me", min_values=3, max_values=12
            )
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert component.custom_id == "cust"
        assert component.is_disabled is True
        assert component.placeholder == "place me"
        assert component.min_values == 3
        assert component.max_values == 12

    def test_with_user_menu_descriptor_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_user_menu
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert component.custom_id == "rPb>^awjHi"
        assert component.is_disabled is False
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1

    @pytest.mark.asyncio()
    async def test_with_user_menu_descriptor_when_called_as_a_method(self):
        mock_callback = mock.AsyncMock()
        mock_ctx = mock.Mock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_user_menu
            async def on_user_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                await mock_callback(self, ctx)

        column = Column()

        await column.on_user_menu(mock_ctx)

        mock_callback.assert_awaited_once_with(column, mock_ctx)

    @pytest.mark.asyncio()
    async def test_with_user_menu_descriptor_when_accessed_on_class(self):
        mock_callback = mock.AsyncMock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            on_user_menu = yuyo.components.as_user_menu(mock_callback)

        assert Column.on_user_menu is mock_callback

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
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert component.custom_id == "cust"
        assert component.is_disabled is True
        assert component.placeholder == "place me"
        assert component.min_values == 3
        assert component.max_values == 12

    def test_with_select_menu_descriptor_with_defaults(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_select_menu(hikari.ComponentType.ROLE_SELECT_MENU)
            async def on_select_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                ...

        rows = Column().rows

        assert len(rows) == 1
        assert len(rows[0].components) == 1
        component = rows[0].components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.ROLE_SELECT_MENU
        assert component.custom_id == "CG4g0;r3<X"
        assert component.is_disabled is False
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1

    @pytest.mark.asyncio()
    async def test_with_select_menu_descriptor_when_called_as_a_method(self):
        mock_callback = mock.AsyncMock()
        mock_ctx = mock.Mock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_select_menu(hikari.ComponentType.USER_SELECT_MENU)
            async def on_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                await mock_callback(self, ctx)

        column = Column()

        await column.on_menu(mock_ctx)

        mock_callback.assert_awaited_once_with(column, mock_ctx)

    @pytest.mark.asyncio()
    async def test_with_select_menu_descriptor_when_accessed_on_class(self):
        mock_callback = mock.AsyncMock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            on_menu = yuyo.components.as_select_menu(hikari.ComponentType.ROLE_SELECT_MENU)(mock_callback)

        assert Column.on_menu is mock_callback

    def test_with_channel_menu_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_channel_menu(
                channel_types=[hikari.PrivateChannel, hikari.ChannelType.GUILD_NEWS],
                custom_id="meed",
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
        assert component.custom_id == "meed"
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
        assert component.custom_id == "hxh5C4S-F$"
        assert component.channel_types == []
        assert component.is_disabled is False
        assert component.placeholder is hikari.UNDEFINED
        assert component.min_values == 0
        assert component.max_values == 1

    @pytest.mark.asyncio()
    async def test_with_channel_menu_descriptor_when_called_as_a_method(self):
        mock_callback = mock.AsyncMock()
        mock_ctx = mock.Mock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_channel_menu
            async def on_channel_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                await mock_callback(self, ctx)

        column = Column()

        await column.on_channel_menu(mock_ctx)

        mock_callback.assert_awaited_once_with(column, mock_ctx)

    @pytest.mark.asyncio()
    async def test_with_channel_menu_descriptor_when_accessed_on_class(self):
        mock_callback = mock.AsyncMock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            on_channel_menu = yuyo.components.as_channel_menu(mock_callback)

        assert Column.on_channel_menu is mock_callback

    def test_with_text_menu_descriptor(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_text_menu(
                custom_id="NiTi",
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
        assert component.custom_id == "NiTi"
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
        assert component.custom_id == "r&bTN$Juxi"
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

    @pytest.mark.asyncio()
    async def test_with_text_menu_descriptor_when_called_as_a_method(self):
        mock_callback = mock.AsyncMock()
        mock_ctx = mock.Mock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_text_menu
            async def on_text_menu(self, ctx: yuyo.components.ComponentContext) -> None:
                await mock_callback(self, ctx)

        column = Column()

        await column.on_text_menu(mock_ctx)

        mock_callback.assert_awaited_once_with(column, mock_ctx)

    @pytest.mark.asyncio()
    async def test_with_text_menu_descriptor_when_accessed_on_class(self):
        mock_callback = mock.AsyncMock()

        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            on_text_menu = yuyo.components.as_text_menu(mock_callback)

        assert Column.on_text_menu is mock_callback

    def test_static_button_row_behaviour(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.DANGER, label="correct")
            async def button_00(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="thai")
            async def button_01(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SECONDARY, label="thigh")
            async def button_02(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SECONDARY, label="meow")
            async def button_03(self, ctx: yuyo.components.Context) -> None:
                ...

            button_04 = yuyo.components.link_button("https://example.com", label="op")

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SUCCESS, label="stare")
            async def button_05(self, ctx: yuyo.components.Context) -> None:
                ...

            button_06 = yuyo.components.link_button("https://example.com/nyaa", label="Lia")

            button_07 = yuyo.components.link_button("https://example.com/meow", label="Omfie")

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SUCCESS, label="nyaa")
            async def button_08(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.DANGER, label="doctor")
            async def button_09(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="wow")
            async def button_10(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SUCCESS, label="he")
            async def button_11(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="sucks")
            async def button_12(self, ctx: yuyo.components.Context) -> None:
                ...

            button_13 = yuyo.components.link_button("https://example.com/davinci", label="de")

        column = Column()

        assert len(column.rows) == 3

        row = column.rows[0]
        assert len(row.components) == 5
        assert isinstance(row.components[0], hikari.api.InteractiveButtonBuilder)
        assert row.components[0].label == "correct"
        assert isinstance(row.components[1], hikari.api.InteractiveButtonBuilder)
        assert row.components[1].label == "thai"
        assert isinstance(row.components[2], hikari.api.InteractiveButtonBuilder)
        assert row.components[2].label == "thigh"
        assert isinstance(row.components[3], hikari.api.InteractiveButtonBuilder)
        assert row.components[3].label == "meow"
        assert isinstance(row.components[4], hikari.api.LinkButtonBuilder)
        assert row.components[4].label == "op"

        row = column.rows[1]
        assert len(row.components) == 5
        row.components[0]
        assert isinstance(row.components[0], hikari.api.InteractiveButtonBuilder)
        assert row.components[0].label == "stare"
        row.components[1]
        assert isinstance(row.components[1], hikari.api.LinkButtonBuilder)
        assert row.components[1].label == "Lia"
        row.components[2]
        assert isinstance(row.components[2], hikari.api.LinkButtonBuilder)
        assert row.components[2].label == "Omfie"
        row.components[3]
        assert isinstance(row.components[3], hikari.api.InteractiveButtonBuilder)
        assert row.components[3].label == "nyaa"
        row.components[4]
        assert isinstance(row.components[4], hikari.api.InteractiveButtonBuilder)
        assert row.components[4].label == "doctor"

        row = column.rows[2]
        assert len(row.components) == 4
        row.components[0]
        assert isinstance(row.components[0], hikari.api.InteractiveButtonBuilder)
        assert row.components[0].label == "wow"
        row.components[1]
        assert isinstance(row.components[1], hikari.api.InteractiveButtonBuilder)
        assert row.components[1].label == "he"
        row.components[2]
        assert isinstance(row.components[2], hikari.api.InteractiveButtonBuilder)
        assert row.components[2].label == "sucks"
        row.components[3]
        assert isinstance(row.components[3], hikari.api.LinkButtonBuilder)
        assert row.components[3].label == "de"

    def test_static_select_menu_row_behaviour(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_role_menu
            async def select_menu_0(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_channel_menu()
            async def select_menu_1(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.with_option("e", "f")
            @yuyo.components.with_option("c", "d")
            @yuyo.components.with_option("a", "b")
            @yuyo.components.as_text_menu()
            async def select_menu_2(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_user_menu
            async def select_menu_3(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_mentionable_menu
            async def select_menu_4(self, ctx: yuyo.components.Context) -> None:
                ...

        column = Column()

        assert len(column.rows) == 5

        row = column.rows[0]
        assert len(row.components) == 1
        assert isinstance(row.components[0], hikari.api.SelectMenuBuilder)
        assert row.components[0].type is hikari.ComponentType.ROLE_SELECT_MENU

        row = column.rows[1]
        assert len(row.components) == 1
        assert isinstance(row.components[0], hikari.api.SelectMenuBuilder)
        assert row.components[0].type is hikari.ComponentType.CHANNEL_SELECT_MENU

        row = column.rows[2]
        assert len(row.components) == 1
        assert isinstance(row.components[0], hikari.api.SelectMenuBuilder)
        assert row.components[0].type is hikari.ComponentType.TEXT_SELECT_MENU

        row = column.rows[3]
        assert len(row.components) == 1
        assert isinstance(row.components[0], hikari.api.SelectMenuBuilder)
        assert row.components[0].type is hikari.ComponentType.USER_SELECT_MENU

        row = column.rows[4]
        assert len(row.components) == 1
        assert isinstance(row.components[0], hikari.api.SelectMenuBuilder)
        assert row.components[0].type is hikari.ComponentType.MENTIONABLE_SELECT_MENU

    def test_mixed_static_row_behaviour(self):
        class Column(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.DANGER, label="cc")
            async def button_0(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="be")
            async def button_1(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SECONDARY, label="the")
            async def button_2(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SECONDARY, label="cat")
            async def button_3(self, ctx: yuyo.components.Context) -> None:
                ...

            button_4 = yuyo.components.link_button("https://example.com", label="girl")

            @yuyo.components.as_role_menu
            async def select_menu_0(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SUCCESS, label="meow")
            async def button_6(self, ctx: yuyo.components.Context) -> None:
                ...

            button_7 = yuyo.components.link_button("https://example.com", label="me")

            @yuyo.components.as_channel_menu()
            async def select_menu_1(self, ctx: yuyo.components.Context) -> None:
                ...

        column = Column()

        assert len(column.rows) == 4

        row = column.rows[0]
        assert len(row.components) == 5
        assert isinstance(row.components[0], hikari.api.InteractiveButtonBuilder)
        assert row.components[0].label == "cc"
        assert isinstance(row.components[1], hikari.api.InteractiveButtonBuilder)
        assert row.components[1].label == "be"
        assert isinstance(row.components[2], hikari.api.InteractiveButtonBuilder)
        assert row.components[2].label == "the"
        assert isinstance(row.components[3], hikari.api.InteractiveButtonBuilder)
        assert row.components[3].label == "cat"
        assert isinstance(row.components[4], hikari.api.LinkButtonBuilder)
        assert row.components[4].label == "girl"

        row = column.rows[1]
        assert len(row.components) == 1
        assert isinstance(row.components[0], hikari.api.SelectMenuBuilder)
        assert row.components[0].type is hikari.ComponentType.ROLE_SELECT_MENU

        row = column.rows[2]
        assert len(row.components) == 2
        assert isinstance(row.components[0], hikari.api.InteractiveButtonBuilder)
        assert row.components[0].label == "meow"
        assert isinstance(row.components[1], hikari.api.LinkButtonBuilder)
        assert row.components[1].label == "me"

        row = column.rows[3]
        assert len(row.components) == 1
        assert isinstance(row.components[0], hikari.api.SelectMenuBuilder)
        assert row.components[0].type is hikari.ComponentType.CHANNEL_SELECT_MENU

    def test_inheritance(self) -> None:
        class Column1(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            link_button = yuyo.components.link_button("https://example.com/br", label="br")

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SUCCESS, label="beepy")
            async def beepy_button(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="aaaa")
            async def a_button(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SECONDARY, label="butt no")
            async def button(self, ctx: yuyo.components.Context) -> None:
                ...

            another_link_button = yuyo.components.link_button("https://example.com/beep", label="beep")

        class Column2(Column1):
            __slots__ = ()

            @yuyo.components.as_channel_menu(custom_id="Chan")
            async def channel_select(self, ctx: yuyo.components.Context) -> None:
                ...

        class Column3(Column2):
            __slots__ = ()

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.DANGER, label="butt")
            async def butt_on(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.DANGER, label="blazy")
            async def blazy_button(self, ctx: yuyo.components.Context) -> None:
                ...

            link_me = yuyo.components.link_button("https://example.com/meep", label="meepo")

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SUCCESS, label="x")
            async def x_button(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="xx butt")
            async def xx_button(self, ctx: yuyo.components.Context) -> None:
                ...

        class Column4(Column3):
            __slots__ = ()

            @yuyo.components.as_user_menu(custom_id="aaaeeeeaaaa")
            async def user_select(self, ctx: yuyo.components.Context) -> None:
                ...

        column = Column4()

        assert len(column.rows) == 4

        row = column.rows[0]
        assert len(row.components) == 5
        component = row.components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.label == "br"
        component = row.components[1]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "beepy"
        component = row.components[2]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "aaaa"
        component = row.components[3]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "butt no"
        component = row.components[4]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.label == "beep"

        row = column.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.ChannelSelectMenuBuilder)
        assert component.custom_id == "Chan"

        row = column.rows[2]
        assert len(row.components) == 5
        component = row.components[0]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "butt"
        component = row.components[1]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "blazy"
        component = row.components[2]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.label == "meepo"
        component = row.components[3]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "x"
        component = row.components[4]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "xx butt"

        row = column.rows[3]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.custom_id == "aaaeeeeaaaa"

    def test_inheritance_with_incomplete_button_row(self) -> None:
        class Column1(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            link_button = yuyo.components.link_button("https://example.com/br", label="br")

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="disco")
            async def a_button(self, ctx: yuyo.components.Context) -> None:
                ...

        class Column2(Column1):
            __slots__ = ()

            @yuyo.components.as_channel_menu(custom_id="yeet")
            async def channel_menu(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SUCCESS, label="usm")
            async def b_button(self, ctx: yuyo.components.Context) -> None:
                ...

        column = Column2()

        assert len(column.rows) == 3

        row = column.rows[0]
        assert len(row.components) == 2
        component = row.components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.label == "br"
        component = row.components[1]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "disco"

        row = column.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.ChannelSelectMenuBuilder)
        assert component.custom_id == "yeet"

        row = column.rows[2]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "usm"

    def test_inheritance_overflows_buttons(self) -> None:
        class Column1(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.DANGER, label="dag")
            async def other_button(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SUCCESS, label="succ")
            async def a_button(self, ctx: yuyo.components.Context) -> None:
                ...

            l_button = yuyo.components.link_button("https://example.com", label="basson")

        class Column2(Column1):
            __slots__ = ()

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="prim")
            async def new_button(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SECONDARY, label="sec")
            async def e_button(self, ctx: yuyo.components.Context) -> None:
                ...

            new_l = yuyo.components.link_button("https://example.com/e", label="suninthesky")

        column = Column2()

        assert len(column.rows) == 2

        row = column.rows[0]
        assert len(row.components) == 5
        component = row.components[0]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "dag"
        component = row.components[1]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "succ"
        component = row.components[2]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.label == "basson"
        component = row.components[3]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "prim"
        component = row.components[4]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "sec"

        row = column.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.label == "suninthesky"

    def test_inheritance_with_menus(self) -> None:
        class Column1(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.with_option("b", "c")
            @yuyo.components.with_option("a", "b")
            @yuyo.components.as_text_menu(custom_id="yeet")
            async def text_select(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_role_menu(custom_id="meat")
            async def role_select(self, ctx: yuyo.components.Context) -> None:
                ...

        class Column2(Column1):
            __slots__ = ()

            @yuyo.components.as_user_menu(custom_id="beep")
            async def user_select(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_channel_menu(custom_id="meow")
            async def channel_select(self, ctx: yuyo.components.Context) -> None:
                ...

        column = Column2()

        assert len(column.rows) == 4

        row = column.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextSelectMenuBuilder)
        assert component.custom_id == "yeet"

        row = column.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.custom_id == "meat"

        row = column.rows[2]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.custom_id == "beep"

        row = column.rows[3]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.ChannelSelectMenuBuilder)
        assert component.custom_id == "meow"

    def test_mixed_inheritance(self) -> None:
        class Column1(yuyo.components.ActionColumnExecutor):
            link_button = yuyo.components.link_button("https://example.com/link", label="lalala")

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="aae")
            async def e_button(self, ctx: yuyo.components.Context) -> None:
                ...

        class Column2(yuyo.components.ActionColumnExecutor):
            @yuyo.components.as_user_menu(custom_id="iou")
            async def user_select(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SECONDARY, label="air")
            async def a_button(self, ctx: yuyo.components.Context) -> None:
                ...

        class Column3(yuyo.components.ActionColumnExecutor):
            @yuyo.components.as_interactive_button(hikari.ButtonStyle.SECONDARY, label="show time")
            async def f_button(self, ctx: yuyo.components.Context) -> None:
                ...

        class MixedColumn(Column3, Column2, Column1):
            ...

        column = MixedColumn()

        assert len(column.rows) == 3

        row = column.rows[0]
        assert len(row.components) == 2
        component = row.components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.label == "lalala"
        component = row.components[1]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "aae"

        row = column.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.custom_id == "iou"

        row = column.rows[2]
        assert len(row.components) == 2
        component = row.components[0]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "air"
        component = row.components[1]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.label == "show time"

    def test_overriding_behaviour(self):
        class ParentColumn(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_user_menu(custom_id="aaaaa", placeholder="place", min_values=1, max_values=5)
            async def on_a_select_menu(self, ctx: yuyo.components.Context) -> None:
                ...

            link_button = yuyo.components.link_button("https://example.com/freaky", emoji="e", label="lab")

            @yuyo.components.as_interactive_button(
                hikari.ButtonStyle.PRIMARY, custom_id="123", emoji="o", label="lab man"
            )
            async def meowy_button(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_channel_menu(
                custom_id="cust",
                channel_types=[hikari.ChannelType.GUILD_TEXT],
                placeholder="meow",
                min_values=4,
                max_values=7,
            )
            async def chan_chan(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.with_option("name", "value")
            @yuyo.components.with_option("op", "boop")
            @yuyo.components.with_option("no", "way")
            @yuyo.components.as_text_menu(custom_id="custard", placeholder="hold", min_values=1, max_values=3)
            async def tt_menu(self, ctx: yuyo.components.Context) -> None:
                ...

        class Column(ParentColumn):
            __slots__ = ()

            @yuyo.components.as_channel_menu(
                custom_id="nop",
                channel_types=[hikari.ChannelType.GUILD_FORUM],
                placeholder="noooo",
                min_values=4,
                max_values=16,
            )
            async def chan_chan(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(
                hikari.ButtonStyle.SECONDARY, custom_id="981", emoji="u", label="lab woman", is_disabled=True
            )
            async def meowy_button(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_user_menu(
                custom_id="op", placeholder="no", min_values=5, max_values=9, is_disabled=True
            )
            async def on_a_select_menu(self, ctx: yuyo.components.Context) -> None:
                ...

            link_button = yuyo.components.link_button(
                "https://example.com/beaky", emoji="usa", label="remix", is_disabled=True
            )

            new_butt = yuyo.components.link_button("https://example.com/new", label="new")

        parent_column = ParentColumn()

        assert len(parent_column.rows) == 4

        row = parent_column.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert component.custom_id == "aaaaa"
        assert component.placeholder == "place"
        assert component.min_values == 1
        assert component.max_values == 5
        assert component.is_disabled is False

        row = parent_column.rows[1]
        assert len(row.components) == 2
        component = row.components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.url == "https://example.com/freaky"
        assert component.emoji == "e"
        assert component.label == "lab"
        assert component.is_disabled is False

        component = row.components[1]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.style is hikari.ButtonStyle.PRIMARY
        assert component.custom_id == "123"
        assert component.emoji == "o"
        assert component.label == "lab man"
        assert component.is_disabled is False

        row = parent_column.rows[2]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.ChannelSelectMenuBuilder)
        assert component.custom_id == "cust"
        assert component.channel_types == [hikari.ChannelType.GUILD_TEXT]
        assert component.placeholder == "meow"
        assert component.min_values == 4
        assert component.max_values == 7

        row = parent_column.rows[3]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextSelectMenuBuilder)
        assert component.custom_id == "custard"
        assert component.placeholder == "hold"
        assert component.min_values == 1
        assert component.max_values == 3
        assert component.options == [
            hikari.impl.SelectOptionBuilder(label="no", value="way"),
            hikari.impl.SelectOptionBuilder(label="op", value="boop"),
            hikari.impl.SelectOptionBuilder(label="name", value="value"),
        ]

        column = Column()

        assert len(column.rows) == 5

        row = column.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert component.custom_id == "op"
        assert component.placeholder == "no"
        assert component.min_values == 5
        assert component.max_values == 9
        assert component.is_disabled is True

        row = column.rows[1]
        assert len(row.components) == 2
        component = row.components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.url == "https://example.com/beaky"
        assert component.emoji == "usa"
        assert component.label == "remix"
        assert component.is_disabled is True

        component = row.components[1]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.style is hikari.ButtonStyle.SECONDARY
        assert component.custom_id == "981"
        assert component.emoji == "u"
        assert component.label == "lab woman"
        assert component.is_disabled is True

        row = column.rows[2]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.ChannelSelectMenuBuilder)
        assert component.custom_id == "nop"
        assert component.channel_types == [hikari.ChannelType.GUILD_FORUM]
        assert component.placeholder == "noooo"
        assert component.min_values == 4
        assert component.max_values == 16

        row = column.rows[3]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextSelectMenuBuilder)
        assert component.custom_id == "custard"
        assert component.placeholder == "hold"
        assert component.min_values == 1
        assert component.max_values == 3
        assert component.options == [
            hikari.impl.SelectOptionBuilder(label="no", value="way"),
            hikari.impl.SelectOptionBuilder(label="op", value="boop"),
            hikari.impl.SelectOptionBuilder(label="name", value="value"),
        ]

        row = column.rows[4]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.url == "https://example.com/new"
        assert component.label == "new"

    def test_overriding_with_not_implemented(self):
        class ParentColumn(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            @yuyo.components.as_user_menu
            async def on_a_select_menu(self, ctx: yuyo.components.Context) -> None:
                ...

            link_button = yuyo.components.link_button("https://freaky")

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY)
            async def meowy_button(self, ctx: yuyo.components.Context) -> None:
                ...

        class Column(ParentColumn):
            __slots__ = ()

            on_a_select_menu = NotImplemented
            link_button = NotImplemented
            meowy_button = NotImplemented

        assert ParentColumn().rows
        assert not Column().rows

    def test_overriding_mixed(self):
        class ParentColumn(yuyo.components.ActionColumnExecutor):
            __slots__ = ()

            link_button = yuyo.components.link_button("https://freaky")

            @yuyo.components.as_user_menu(custom_id="hey!")
            async def on_a_select_menu(self, ctx: yuyo.components.Context) -> None:
                ...

            @yuyo.components.as_interactive_button(hikari.ButtonStyle.PRIMARY, label="meow")
            async def meowy_button(self, ctx: yuyo.components.Context) -> None:
                ...

        class Column(ParentColumn):
            __slots__ = ()

            on_a_select_menu = NotImplemented

            @yuyo.components.as_channel_menu(custom_id="custoard")
            async def channel_menu(self, ctx: yuyo.components.Context) -> None:
                ...

            link_button = yuyo.components.link_button("https://example.com/l")

        parent_column = ParentColumn()

        assert len(parent_column.rows) == 3

        row = parent_column.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.url == "https://freaky"

        row = parent_column.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.SelectMenuBuilder)
        assert component.type is hikari.ComponentType.USER_SELECT_MENU
        assert component.custom_id == "hey!"

        row = parent_column.rows[2]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.style is hikari.ButtonStyle.PRIMARY
        assert component.label == "meow"

        assert len(parent_column.rows) == 3

        column = Column()

        assert len(column.rows) == 2

        row = column.rows[0]
        assert len(row.components) == 2
        component = row.components[0]
        assert isinstance(component, hikari.api.LinkButtonBuilder)
        assert component.url == "https://example.com/l"

        component = row.components[1]
        assert isinstance(component, hikari.api.InteractiveButtonBuilder)
        assert component.style is hikari.ButtonStyle.PRIMARY
        assert component.label == "meow"

        row = column.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.ChannelSelectMenuBuilder)
        assert component.custom_id == "custoard"


def test_ensure_parse_channel_types_has_every_channel_class():
    for _, attribute in inspect.getmembers(hikari):
        if isinstance(attribute, type) and issubclass(attribute, hikari.PartialChannel):
            result = yuyo.components._parse_channel_types(attribute)

            assert result
