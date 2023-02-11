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

import typing
from unittest import mock

import hikari
import hikari.api  # TODO: import temporarily needed to missing impl exports.
import hikari.api.special_endpoints  # TODO: import temporarily needed to missing impl exports.
import hikari.components  # TODO: import temporarily needed due to hikari not exporting TL.
import pytest

import yuyo


@pytest.mark.parametrize(
    ("cmd_type", "expected_cls"),
    [
        (hikari.CommandType.MESSAGE, hikari.api.ContextMenuCommandBuilder),
        (hikari.CommandType.SLASH, hikari.api.SlashCommandBuilder),
        (hikari.CommandType.USER, hikari.api.ContextMenuCommandBuilder),
    ],
)
def test_to_cmd_builder(cmd_type: hikari.CommandType, expected_cls: type[hikari.api.CommandBuilder]):
    result = yuyo.to_builder.to_cmd_builder(
        mock.Mock(type=cmd_type, name_localizations={}, description_localizations={}, options=[])
    )

    assert isinstance(result, expected_cls)


def test_to_cmd_builder_with_unknown_cmd_type():
    mock_cmd = mock.Mock(type=123321123)

    with pytest.raises(NotImplementedError, match="123321123"):
        yuyo.to_builder.to_cmd_builder(mock_cmd)


def test_to_slash_cmd_builder():
    mock_slash_cmd = hikari.SlashCommand(
        app=mock.Mock(),
        id=hikari.Snowflake(54123),
        type=hikari.CommandType.SLASH,
        application_id=hikari.Snowflake(675234),
        name="adsaasd",
        default_member_permissions=hikari.Permissions(341),
        is_dm_enabled=mock.Mock(),
        is_nsfw=mock.Mock(),
        guild_id=hikari.Snowflake(6541234123),
        version=hikari.Snowflake(54123),
        name_localizations={hikari.Locale.BG: "sa", hikari.Locale.PT_BR: "42342sdsaasd"},
        description="56234123432123",
        description_localizations={hikari.Locale.DE: "dsjjqwe", hikari.Locale.EN_GB: "roikweioji"},
        options=None,
    )

    result = yuyo.to_builder.to_slash_cmd_builder(mock_slash_cmd)

    assert result.name is mock_slash_cmd.name
    assert result.description is mock_slash_cmd.description
    assert result.options == []
    assert result.id is mock_slash_cmd.id
    assert result.default_member_permissions is mock_slash_cmd.default_member_permissions
    assert result.is_dm_enabled is mock_slash_cmd.is_dm_enabled
    assert result.is_nsfw is mock_slash_cmd.is_nsfw
    assert result.name_localizations == mock_slash_cmd.name_localizations
    assert result.name_localizations is not mock_slash_cmd.name_localizations
    assert result.description_localizations == mock_slash_cmd.description_localizations
    assert result.description_localizations is not mock_slash_cmd.description_localizations


def test_to_slash_cmd_builder_with_options():
    mock_option_1 = hikari.CommandOption(
        type=hikari.OptionType.USER,
        name="polgfokpfgdokdsfokp",
        description="546142sadasd",
        description_localizations={hikari.Locale.JA: "jajaja"},
        channel_types=[hikari.ChannelType.GUILD_FORUM, hikari.ChannelType.GUILD_NEWS_THREAD],
        choices=[hikari.CommandChoice(name="hi", value="bye"), hikari.CommandChoice(name="x", value="d")],
        name_localizations={hikari.Locale.FI: "finished", hikari.Locale.BG: "background"},
    )
    mock_option_2 = hikari.CommandOption(
        type=hikari.OptionType.MENTIONABLE,
        name="ldfslkfdskldsf",
        description="dflokdfpiqwe3",
        description_localizations={hikari.Locale.HR: "sheeeeeeeeeeeeeeeeeeeeeeeeeeeeeeera"},
        name_localizations={hikari.Locale.CS: "Cope"},
    )
    mock_slash_cmd = hikari.SlashCommand(
        app=mock.Mock(),
        id=hikari.Snowflake(123321123),
        type=hikari.CommandType.SLASH,
        application_id=hikari.Snowflake(12345123123),
        default_member_permissions=hikari.Permissions(123321),
        is_dm_enabled=mock.Mock(),
        is_nsfw=mock.Mock(),
        guild_id=hikari.Snowflake(67234123),
        version=hikari.Snowflake(123321123),
        name="tdfdsdfasd",
        name_localizations={},
        description="gfdfsfdsfd",
        description_localizations={},
        options=[mock_option_1, mock_option_2],
    )

    result = yuyo.to_builder.to_slash_cmd_builder(mock_slash_cmd)

    assert len(result.options) == 2
    option = result.options[0]
    assert option is not mock_option_1
    assert option.type is mock_option_1.type
    assert option.name is mock_option_1.name
    assert option.description is mock_option_1.description
    assert option.is_required is mock_option_1.is_required
    assert option.choices == mock_option_1.choices
    assert option.options is not mock_option_1.choices
    assert option.choices
    assert mock_option_1.choices
    assert not any(choice is other for choice, other in zip(option.choices, mock_option_1.choices))
    assert option.channel_types == mock_option_1.channel_types
    assert option.channel_types is not mock_option_1.channel_types
    assert option.autocomplete is mock_option_1.autocomplete
    assert option.min_value is mock_option_1.min_value
    assert option.max_value is mock_option_1.max_value
    assert option.name_localizations == mock_option_1.name_localizations
    assert option.name_localizations is not mock_option_1.name_localizations
    assert option.description_localizations == mock_option_1.description_localizations
    assert option.description_localizations is not mock_option_1.description_localizations
    assert option.min_length is mock_option_1.min_length
    assert option.max_length is mock_option_1.max_length

    option = result.options[1]
    assert option is not mock_option_2
    assert option.type is mock_option_2.type
    assert option.name is mock_option_2.name
    assert option.description is mock_option_2.description
    assert option.is_required is mock_option_2.is_required
    assert option.choices is None
    assert option.options is None
    assert option.channel_types is None
    assert option.autocomplete is mock_option_2.autocomplete
    assert option.min_value is mock_option_2.min_value
    assert option.max_value is mock_option_2.max_value
    assert option.name_localizations == mock_option_2.name_localizations
    assert option.name_localizations is not mock_option_2.name_localizations
    assert option.description_localizations == mock_option_2.description_localizations
    assert option.description_localizations is not mock_option_2.description_localizations
    assert option.min_length is mock_option_2.min_length
    assert option.max_length is mock_option_2.max_length


def test_to_slash_cmd_builder_with_nested_options():
    mock_option_1 = hikari.CommandOption(
        type=hikari.OptionType.CHANNEL,
        name="fdkklfd",
        description="adsdsasd",
        description_localizations={hikari.Locale.JA: "jajaja"},
        channel_types=[hikari.ChannelType.GUILD_FORUM, hikari.ChannelType.GUILD_NEWS_THREAD],
        choices=[hikari.CommandChoice(name="hi", value="bye"), hikari.CommandChoice(name="x", value="d")],
        name_localizations={hikari.Locale.FI: "finished", hikari.Locale.BG: "background"},
    )
    mock_option_2 = hikari.CommandOption(
        type=hikari.OptionType.USER,
        name="asddsaasd",
        description="£gl;f;lfgdlk;",
        description_localizations={hikari.Locale.HR: "sheeeeeeeeeeeeeeeeeeeeeeeeeeeeeeera"},
        name_localizations={hikari.Locale.CS: "Cope"},
    )
    mock_cmd_option = hikari.CommandOption(
        type=hikari.OptionType.SUB_COMMAND,
        name="fddfasd",
        description="p[342pol34po123",
        options=[mock_option_1, mock_option_2],
    )
    mock_slash_cmd = hikari.SlashCommand(
        app=mock.Mock(),
        id=hikari.Snowflake(123321123),
        type=hikari.CommandType.SLASH,
        application_id=hikari.Snowflake(43123123123),
        name="43123123123",
        name_localizations={},
        default_member_permissions=hikari.Permissions(341213123),
        is_dm_enabled=mock.Mock(),
        is_nsfw=mock.Mock(),
        guild_id=hikari.Snowflake(12332123123),
        version=hikari.Snowflake(54123123123),
        description="3412312132123132312ewaadsdsa",
        description_localizations={},
        options=[mock_cmd_option],
    )

    result = yuyo.to_builder.to_slash_cmd_builder(mock_slash_cmd)

    assert len(result.options) == 1
    assert result.options[0].options

    assert len(result.options[0].options) == 2
    option = result.options[0].options[0]
    assert option is not mock_option_1
    assert option.type is mock_option_1.type
    assert option.name is mock_option_1.name
    assert option.description is mock_option_1.description
    assert option.is_required is mock_option_1.is_required
    assert option.choices == mock_option_1.choices
    assert option.options is not mock_option_1.choices
    assert option.choices
    assert mock_option_1.choices
    assert not any(choice is other for choice, other in zip(option.choices, mock_option_1.choices))
    assert option.channel_types == mock_option_1.channel_types
    assert option.channel_types is not mock_option_1.channel_types
    assert option.autocomplete is mock_option_1.autocomplete
    assert option.min_value is mock_option_1.min_value
    assert option.max_value is mock_option_1.max_value
    assert option.name_localizations == mock_option_1.name_localizations
    assert option.name_localizations is not mock_option_1.name_localizations
    assert option.description_localizations == mock_option_1.description_localizations
    assert option.description_localizations is not mock_option_1.description_localizations
    assert option.min_length is mock_option_1.min_length
    assert option.max_length is mock_option_1.max_length

    option = result.options[0].options[1]
    assert option is not mock_option_2
    assert option.type is mock_option_2.type
    assert option.name is mock_option_2.name
    assert option.description is mock_option_2.description
    assert option.is_required is mock_option_2.is_required
    assert option.choices is None
    assert option.options is None
    assert option.channel_types is None
    assert option.autocomplete is mock_option_2.autocomplete
    assert option.min_value is mock_option_2.min_value
    assert option.max_value is mock_option_2.max_value
    assert option.name_localizations == mock_option_2.name_localizations
    assert option.name_localizations is not mock_option_2.name_localizations
    assert option.description_localizations == mock_option_2.description_localizations
    assert option.description_localizations is not mock_option_2.description_localizations
    assert option.min_length is mock_option_2.min_length
    assert option.max_length is mock_option_2.max_length


def test_to_slash_cmd_builder_with_double_nested_options():
    mock_option_1 = hikari.CommandOption(
        type=hikari.OptionType.MENTIONABLE,
        name="fdfgkfgjdiowoieroiroqoqwoeewq",
        description="gffgkldgfdlksdjfkqweieuwqio",
        description_localizations={hikari.Locale.JA: "jajaja"},
        channel_types=[hikari.ChannelType.GUILD_FORUM, hikari.ChannelType.GUILD_NEWS_THREAD],
        choices=[hikari.CommandChoice(name="hi", value="bye"), hikari.CommandChoice(name="x", value="d")],
        name_localizations={hikari.Locale.FI: "finished", hikari.Locale.BG: "background"},
    )
    mock_option_2 = hikari.CommandOption(
        name="fdfddsasdasddsfeqwe",
        description="grffghgfdssads",
        type=hikari.OptionType.FLOAT,
        description_localizations={hikari.Locale.HR: "sheeeeeeeeeeeeeeeeeeeeeeeeeeeeeeera"},
        name_localizations={hikari.Locale.CS: "Cope"},
    )
    mock_nested_cmd_option = hikari.CommandOption(
        type=hikari.OptionType.SUB_COMMAND,
        name="hhsaddsa",
        description="gffgsdsf",
        options=[mock_option_1, mock_option_2],
    )
    mock_cmd_option = hikari.CommandOption(
        type=hikari.OptionType.SUB_COMMAND_GROUP, name="gfdgasd", description="asddsa", options=[mock_nested_cmd_option]
    )
    mock_slash_cmd = hikari.SlashCommand(
        app=mock.Mock(),
        id=hikari.Snowflake(3412123123),
        application_id=hikari.Snowflake(543123123),
        type=hikari.CommandType.SLASH,
        default_member_permissions=hikari.Permissions(43512),
        is_dm_enabled=mock.Mock(),
        is_nsfw=mock.Mock(),
        guild_id=hikari.Snowflake(123123321),
        version=hikari.Snowflake(123321123321),
        name="dffsdasd",
        name_localizations={},
        description="gf';l';re-pewp[r",
        description_localizations={},
        options=[mock_cmd_option],
    )

    result = yuyo.to_builder.to_slash_cmd_builder(mock_slash_cmd)

    assert len(result.options) == 1
    assert result.options[0].options
    assert len(result.options[0].options) == 1
    assert result.options[0].options[0].options

    assert len(result.options[0].options[0].options) == 2
    option = result.options[0].options[0].options[0]
    assert option is not mock_option_1
    assert option.type is mock_option_1.type
    assert option.name is mock_option_1.name
    assert option.description is mock_option_1.description
    assert option.is_required is mock_option_1.is_required
    assert option.choices == mock_option_1.choices
    assert option.options is not mock_option_1.choices
    assert option.choices
    assert mock_option_1.choices
    assert not any(choice is other for choice, other in zip(option.choices, mock_option_1.choices))
    assert option.channel_types == mock_option_1.channel_types
    assert option.channel_types is not mock_option_1.channel_types
    assert option.autocomplete is mock_option_1.autocomplete
    assert option.min_value is mock_option_1.min_value
    assert option.max_value is mock_option_1.max_value
    assert option.name_localizations == mock_option_1.name_localizations
    assert option.name_localizations is not mock_option_1.name_localizations
    assert option.description_localizations == mock_option_1.description_localizations
    assert option.description_localizations is not mock_option_1.description_localizations
    assert option.min_length is mock_option_1.min_length
    assert option.max_length is mock_option_1.max_length

    option = result.options[0].options[0].options[1]
    assert option is not mock_option_2
    assert option.type is mock_option_2.type
    assert option.name is mock_option_2.name
    assert option.description is mock_option_2.description
    assert option.is_required is mock_option_2.is_required
    assert option.choices is None
    assert option.options is None
    assert option.channel_types is None
    assert option.autocomplete is mock_option_2.autocomplete
    assert option.min_value is mock_option_2.min_value
    assert option.max_value is mock_option_2.max_value
    assert option.name_localizations == mock_option_2.name_localizations
    assert option.name_localizations is not mock_option_2.name_localizations
    assert option.description_localizations == mock_option_2.description_localizations
    assert option.description_localizations is not mock_option_2.description_localizations
    assert option.min_length is mock_option_2.min_length
    assert option.max_length is mock_option_2.max_length


def test_to_context_menu_builder():
    mock_cmd = hikari.ContextMenuCommand(
        app=mock.Mock(),
        type=hikari.CommandType.MESSAGE,
        id=hikari.Snowflake(123321123),
        application_id=hikari.Snowflake(12332112),
        name="l435o;ldfl';",
        default_member_permissions=hikari.Permissions(123323434),
        is_dm_enabled=mock.Mock(),
        is_nsfw=mock.Mock(),
        guild_id=hikari.Snowflake(3123312),
        version=hikari.Snowflake(123321),
        name_localizations={hikari.Locale.CS: "gasdas", hikari.Locale.DE: "hgfdasd"},
    )

    result = yuyo.to_builder.to_context_menu_builder(mock_cmd)

    assert result.name is mock_cmd.name
    assert result.type is mock_cmd.type
    assert result.id is mock_cmd.id
    assert result.default_member_permissions is mock_cmd.default_member_permissions
    assert result.is_dm_enabled is mock_cmd.is_dm_enabled
    assert result.is_nsfw is mock_cmd.is_nsfw
    assert result.name_localizations == mock_cmd.name_localizations
    assert result.name_localizations is not mock_cmd.name_localizations


def test_to_msg_action_row_builder():
    mock_interactive_button = hikari.ButtonComponent(
        style=hikari.ButtonStyle.DANGER,
        type=hikari.ComponentType.BUTTON,
        label="fddfasd",
        emoji=mock.Mock(),
        custom_id="tgrfsdfsdfads",
        url=None,
        is_disabled=mock.Mock(),
    )
    mock_link_button = hikari.ButtonComponent(
        style=hikari.ButtonStyle.LINK,
        type=hikari.ComponentType.BUTTON,
        label="ffddfsadsa",
        emoji=mock.Mock(),
        custom_id=None,
        url="htgtppdsps",
        is_disabled=mock.Mock(),
    )
    mock_select_menu = hikari.SelectMenuComponent(
        custom_id="fdkldfkllkdfs",
        placeholder="sdkjjkads",
        min_values=1,
        max_values=22,
        is_disabled=mock.Mock(),
        type=hikari.ComponentType.ROLE_SELECT_MENU,
    )
    mock_text_select_menu = hikari.components.TextSelectMenuComponent(
        custom_id="fdkldfkllkdfs",
        placeholder="sdkjjkads",
        min_values=1,
        max_values=22,
        is_disabled=mock.Mock(),
        options=[mock.Mock()],
        type=hikari.ComponentType.TEXT_SELECT_MENU,
    )
    mock_channel_select_menu = hikari.components.ChannelSelectMenuComponent(
        custom_id="fdkldfkllkdfs",
        channel_types=[123, 432, 3456],
        placeholder="sdkjjkads",
        min_values=1,
        max_values=22,
        is_disabled=mock.Mock(),
        type=hikari.ComponentType.CHANNEL_SELECT_MENU,
    )
    action_row = hikari.MessageActionRowComponent(
        components=[
            mock_interactive_button,
            mock_link_button,
            mock_select_menu,
            mock_text_select_menu,
            mock_channel_select_menu,
        ],
        type=hikari.ComponentType.ACTION_ROW,
    )

    builder = yuyo.to_builder.to_msg_action_row_builder(action_row)

    assert len(builder.components) == 5
    component = builder.components[0]
    assert isinstance(component, hikari.api.InteractiveButtonBuilder)
    assert component.style is mock_interactive_button.style
    assert component.emoji is mock_interactive_button.emoji
    assert component.label is mock_interactive_button.label
    assert component.is_disabled is mock_interactive_button.is_disabled
    assert component.custom_id is mock_interactive_button.custom_id

    component = builder.components[1]
    assert isinstance(component, hikari.api.LinkButtonBuilder)
    assert component.style is mock_link_button.style
    assert component.emoji is mock_link_button.emoji
    assert component.label is mock_link_button.label
    assert component.is_disabled is mock_link_button.is_disabled
    assert component.url is mock_link_button.url

    component = builder.components[2]
    assert isinstance(component, hikari.api.SelectMenuBuilder)
    assert component.custom_id is mock_select_menu.custom_id
    assert component.is_disabled is mock_select_menu.is_disabled
    # assert component.type is mock_select_menu.type  # TODO: missing property
    assert component.placeholder is mock_select_menu.placeholder
    assert component.min_values is mock_select_menu.min_values
    assert component.max_values is mock_select_menu.max_values

    component = builder.components[3]
    assert isinstance(component, hikari.api.special_endpoints.TextSelectMenuBuilder)
    component = typing.cast("hikari.api.special_endpoints.TextSelectMenuBuilder[typing.Any]", component)
    assert component.custom_id is mock_text_select_menu.custom_id
    # assert component.type is hikari.ComponentType.TEXT_SELECT_MENU  # TODO: missing property
    assert component.is_disabled is mock_text_select_menu.is_disabled
    assert len(component.options) == 1
    assert component.options[0].label is mock_text_select_menu.options[0].label
    assert component.options[0].value is mock_text_select_menu.options[0].value
    assert component.options[0].description is mock_text_select_menu.options[0].description
    assert component.options[0].emoji is mock_text_select_menu.options[0].emoji
    assert component.options[0].is_default is mock_text_select_menu.options[0].is_default
    assert component.placeholder is mock_text_select_menu.placeholder
    assert component.min_values is mock_text_select_menu.min_values
    assert component.max_values is mock_text_select_menu.max_values

    component = builder.components[4]
    assert isinstance(component, hikari.api.special_endpoints.ChannelSelectMenuBuilder)
    assert component.channel_types == mock_channel_select_menu.channel_types
    # assert component.type is hikari.ComponentType.CHANNEL_SELECT_MENU  # TODO: missing property
    assert component.custom_id is mock_channel_select_menu.custom_id
    assert component.is_disabled is mock_channel_select_menu.is_disabled
    assert component.placeholder is mock_channel_select_menu.placeholder
    assert component.min_values is mock_channel_select_menu.min_values
    assert component.max_values is mock_channel_select_menu.max_values


def test_to_msg_action_row_builder_when_sub_type_unknown():
    select_menu = mock.Mock(components=[mock.Mock(type=543123)])

    with pytest.raises(NotImplementedError, match="543123"):
        yuyo.to_builder.to_msg_action_row_builder(select_menu)


class TestDummyContainer:
    def test_add_component(self):
        dummy = yuyo.to_builder._DummyContainer()

        with pytest.raises(RuntimeError):
            dummy.add_component(mock.Mock())


def test_to_button_builder_for_link_button():
    mock_button = hikari.ButtonComponent(
        custom_id=None,
        type=hikari.ComponentType.BUTTON,
        url="hpdfpsdpadsp",
        is_disabled=mock.Mock(),
        emoji=None,
        label=None,
        style=hikari.ButtonStyle.LINK,
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.LinkButtonBuilder)
    assert result.style is hikari.ButtonStyle.LINK
    assert result.url is mock_button.url
    assert result.label is hikari.UNDEFINED
    assert result.emoji is hikari.UNDEFINED
    assert "emoji" not in result.build()


def test_to_button_builder_for_link_button_when_all_fields_set():
    mock_button = hikari.ButtonComponent(
        type=hikari.ComponentType.BUTTON,
        label="gkflfgklfgklfgkl",
        url="fdsaasddsa",
        is_disabled=mock.Mock(),
        custom_id=None,
        emoji=hikari.CustomEmoji(id=hikari.Snowflake(65234), name="kon'nichiwa", is_animated=True),
        style=hikari.ButtonStyle.LINK,
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.LinkButtonBuilder)
    assert result.style is hikari.ButtonStyle.LINK
    assert result.url is mock_button.url
    assert result.label is mock_button.label
    assert result.emoji is mock_button.emoji
    assert result.build()["emoji"] == {"id": "65234"}


def test_to_button_builder_for_link_button_when_emoji_is_custom():
    mock_button = hikari.ButtonComponent(
        type=hikari.ComponentType.BUTTON,
        label="fdlkdflkfdl",
        url="kfdkfdjfdkj",
        is_disabled=mock.Mock(),
        custom_id=None,
        emoji=hikari.UnicodeEmoji("bin"),
        style=hikari.ButtonStyle.LINK,
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.LinkButtonBuilder)
    assert result.emoji is mock_button.emoji
    assert result.build()["emoji"] == {"name": "bin"}


@pytest.mark.parametrize("button_style", set(hikari.ButtonStyle).difference({hikari.ButtonStyle.LINK}))
def test_to_button_builder_for_interactive_button(button_style: hikari.ButtonStyle):
    mock_button = hikari.ButtonComponent(
        type=hikari.ComponentType.BUTTON,
        custom_id="fdkdfkllksd",
        is_disabled=mock.Mock(),
        emoji=None,
        label=None,
        style=button_style,
        url=None,
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.InteractiveButtonBuilder)
    assert result.style is button_style
    assert result.custom_id is mock_button.custom_id
    assert result.label is hikari.UNDEFINED
    assert result.is_disabled is mock_button.is_disabled
    assert result.emoji is hikari.UNDEFINED
    assert "emoji" not in result.build()


def test_to_button_builder_for_interactive_button_when_all_fields_set():
    mock_button = hikari.ButtonComponent(
        type=hikari.ComponentType.BUTTON,
        custom_id="gklfgklfgkl",
        label="gjgjjg",
        is_disabled=mock.Mock(),
        emoji=hikari.CustomEmoji(id=hikari.Snowflake(123321), name="hi", is_animated=True),
        style=hikari.ButtonStyle.PRIMARY,
        url=None,
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.InteractiveButtonBuilder)
    assert result.style is mock_button.style
    assert result.custom_id is mock_button.custom_id
    assert result.label is mock_button.label
    assert result.is_disabled is mock_button.is_disabled
    assert result.emoji is mock_button.emoji
    assert result.build()["emoji"] == {"id": "123321"}


def test_to_button_builder_for_interactive_button_when_emoji_is_custom():
    mock_button = hikari.ButtonComponent(
        type=hikari.ComponentType.BUTTON,
        label="hohohoho",
        url=None,
        custom_id="kfdlkfdkfdkjl",
        is_disabled=mock.Mock(),
        emoji=hikari.UnicodeEmoji("meow"),
        style=hikari.ButtonStyle.SECONDARY,
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.InteractiveButtonBuilder)
    assert result.emoji is mock_button.emoji
    assert result.build()["emoji"] == {"name": "meow"}


class TestSelectOptionBuilder:
    def test_set_description(self):
        builder = yuyo.to_builder.to_text_select_menu_builder(mock.Mock(options=[mock.Mock()])).options[0]

        result = builder.set_description("a meow description")

        assert result is builder
        assert builder.description == "a meow description"

    def test_set_description_when_undefined(self):
        builder = (
            yuyo.to_builder.to_text_select_menu_builder(mock.Mock(options=[mock.Mock()]))
            .options[0]
            .set_description("eep")
        )

        result = builder.set_description(hikari.UNDEFINED)

        assert result is builder
        assert builder.description is hikari.UNDEFINED

    @pytest.mark.parametrize("emoji", ["hihi", hikari.UnicodeEmoji("eep")])
    def test_set_emoji_when_unicode_emoji(self, emoji: str):
        builder = yuyo.to_builder.to_text_select_menu_builder(mock.Mock(options=[mock.Mock()])).options[0]

        builder.set_emoji(emoji)

        assert builder.emoji is emoji
        assert builder.build()["emoji"] == {"name": emoji}

    @pytest.mark.parametrize(
        ("emoji", "emoji_id"),
        [
            (hikari.CustomEmoji(id=hikari.Snowflake(4312123), name="h", is_animated=False), "4312123"),
            (56431123, "56431123"),
        ],
    )
    def test_set_emoji_when_custom_emoji(self, emoji: typing.Union[hikari.CustomEmoji, int], emoji_id: str):
        builder = yuyo.to_builder.to_text_select_menu_builder(mock.Mock(options=[mock.Mock()])).options[0]

        builder.set_emoji(emoji)

        assert builder.emoji is emoji
        assert builder.build()["emoji"] == {"id": emoji_id}

    def test_set_emoji_when_undefined(self):
        builder = (
            yuyo.to_builder.to_text_select_menu_builder(mock.Mock(options=[mock.Mock()])).options[0].set_emoji("hi")
        )

        builder.set_emoji(hikari.UNDEFINED)

        assert builder.emoji is hikari.UNDEFINED

    def test_set_is_default(self):
        builder = yuyo.to_builder.to_text_select_menu_builder(mock.Mock(options=[mock.Mock()])).options[0]

        builder.set_is_default(True)

        assert builder.is_default is True

    def test_add_to_menu(self):
        builder = yuyo.to_builder.to_text_select_menu_builder(mock.Mock(options=[mock.Mock()])).options[0]

        with pytest.raises(NotImplementedError):
            builder.add_to_menu()

    def test_build(self):
        builder = yuyo.to_builder.to_text_select_menu_builder(
            mock.Mock(
                options=[
                    hikari.SelectMenuOption(label="meow", value="extra", description=None, emoji=None, is_default=False)
                ]
            )
        ).options[0]

        result = builder.build()

        assert result["label"] == "meow"
        assert result["value"] == "extra"
        assert result["default"] is False
        assert "description" not in result
        assert "emoji" not in result

    def test_build_with_all_fields(self):
        builder = yuyo.to_builder.to_text_select_menu_builder(
            mock.Mock(
                options=[
                    hikari.SelectMenuOption(
                        label="nyaa",
                        value="ners",
                        description="meowy catgirl",
                        emoji=hikari.UnicodeEmoji("x3 nuzzles"),
                        is_default=True,
                    )
                ]
            )
        ).options[0]

        result = builder.build()

        assert result["label"] == "nyaa"
        assert result["value"] == "ners"
        assert result["default"] is True
        assert result["description"] == "meowy catgirl"
        assert result["emoji"] == {"name": "x3 nuzzles"}

    def test_build_with_custom_emoji(self):
        builder = yuyo.to_builder.to_text_select_menu_builder(
            mock.Mock(
                options=[
                    hikari.SelectMenuOption(
                        label="nyaa",
                        value="ners",
                        description=None,
                        emoji=hikari.CustomEmoji(id=hikari.Snowflake(43123), name="e", is_animated=True),
                        is_default=True,
                    )
                ]
            )
        ).options[0]

        result = builder.build()

        assert result["emoji"] == {"id": "43123"}


def test_to_channel_select_menu_builder():
    mock_menu = hikari.components.ChannelSelectMenuComponent(
        type=hikari.ComponentType.CHANNEL_SELECT_MENU,
        channel_types=[hikari.ChannelType.GUILD_NEWS, hikari.ChannelType.GUILD_STAGE],
        custom_id="uyghdfg",
        placeholder="gfdsdfksld",
        min_values=4,
        max_values=12,
        is_disabled=mock.Mock(),
    )

    builder = yuyo.to_builder.to_channel_select_menu_builder(mock_menu)

    # assert builder.type is hikari.ComponentType.CHANNEL_SELECT_MENU  # TODO: missing in hikari
    assert builder.custom_id is mock_menu.custom_id
    assert builder.channel_types == mock_menu.channel_types
    assert builder.placeholder is mock_menu.placeholder
    assert builder.min_values is mock_menu.min_values
    assert builder.max_values is mock_menu.max_values
    assert builder.is_disabled is mock_menu.is_disabled


def test_to_channel_select_menu_builder_when_placeholder_is_none():
    builder = yuyo.to_builder.to_channel_select_menu_builder(mock.Mock(channel_types=[], placeholder=None))

    assert builder.placeholder is hikari.UNDEFINED


def test_to_text_select_menu_builder():
    mock_opt_1 = hikari.SelectMenuOption(
        label="kfdkldfkldfs",
        value="fdldkfjlkjfdsklj",
        description="askldsdlkdas",
        emoji=mock.Mock(),
        is_default=mock.Mock(),
    )
    mock_opt_2 = hikari.SelectMenuOption(
        label="kldfslksdlkds", value="fdkldfkldfslk", description=None, emoji=mock.Mock(), is_default=mock.Mock()
    )
    mock_menu = hikari.components.TextSelectMenuComponent(
        type=hikari.ComponentType.TEXT_SELECT_MENU,
        custom_id="kdsfllkdslkslkda",
        options=[mock_opt_1, mock_opt_2],
        placeholder="fdkldls;ksld",
        min_values=4,
        max_values=22,
        is_disabled=mock.Mock(),
    )

    builder = yuyo.to_builder.to_text_select_menu_builder(mock_menu)

    assert builder.custom_id is mock_menu.custom_id
    assert len(builder.options) == 2

    opt = builder.options[0]
    assert opt.label is mock_opt_1.label
    assert opt.value is mock_opt_1.value
    assert opt.description is mock_opt_1.description
    assert opt.emoji is mock_opt_1.emoji
    assert opt.is_default is mock_opt_1.is_default

    opt = builder.options[1]
    assert opt.label is mock_opt_2.label
    assert opt.value is mock_opt_2.value
    assert opt.description is hikari.UNDEFINED
    assert opt.emoji is mock_opt_2.emoji
    assert opt.is_default is mock_opt_2.is_default

    # assert builder.type is hikari.ComponentType.TEXT_SELECT_MENU  # TODO: missing in hikari
    assert builder.placeholder is mock_menu.placeholder
    assert builder.min_values is mock_menu.min_values
    assert builder.max_values is mock_menu.max_values
    assert builder.is_disabled is mock_menu.is_disabled


def test_to_text_select_menu_builder_when_placeholder_is_none():
    builder = yuyo.to_builder.to_text_select_menu_builder(mock.Mock(options=[], placeholder=None))

    assert builder.placeholder is hikari.UNDEFINED


def test_to_select_menu_builder():
    mock_menu = hikari.SelectMenuComponent(
        type=hikari.ComponentType.ROLE_SELECT_MENU,
        custom_id="123321432",
        placeholder="43123",
        min_values=5,
        max_values=11,
        is_disabled=mock.Mock(),
    )

    builder = yuyo.to_builder.to_select_menu_builder(mock_menu)

    # assert builder.type is mock_menu.custom_id.type  # TODO: missing in hikari
    assert builder.custom_id is mock_menu.custom_id
    assert builder.placeholder is mock_menu.placeholder
    assert builder.min_values is mock_menu.min_values
    assert builder.max_values is mock_menu.max_values
    assert builder.is_disabled is mock_menu.is_disabled


def test_to_select_menu_builder_when_placeholder_is_none():
    builder = yuyo.to_builder.to_select_menu_builder(mock.Mock(placeholder=None))

    assert builder.placeholder is hikari.UNDEFINED


def test_to_select_menu_builder_when_channel():
    mock_menu = hikari.components.ChannelSelectMenuComponent(
        type=hikari.ComponentType.CHANNEL_SELECT_MENU,
        custom_id="123321432",
        channel_types=[],
        placeholder="43123",
        min_values=5,
        max_values=11,
        is_disabled=mock.Mock(),
    )

    builder = yuyo.to_builder.to_select_menu_builder(mock_menu)

    assert isinstance(builder, hikari.api.special_endpoints.ChannelSelectMenuBuilder)
    # assert builder.type is hikari.ComponentType.CHANNEL_SELECT_MENU  # TODO: missing in hikari


def test_to_select_menu_builder_when_text():
    mock_menu = hikari.components.TextSelectMenuComponent(
        type=hikari.ComponentType.TEXT_SELECT_MENU,
        custom_id="123321432",
        options=[],
        placeholder="43123",
        min_values=5,
        max_values=11,
        is_disabled=mock.Mock(),
    )
    builder = yuyo.to_builder.to_select_menu_builder(mock_menu)

    assert isinstance(builder, hikari.api.special_endpoints.TextSelectMenuBuilder)
    # assert builder.type is hikari.ComponentType.TEXT_SELECT_MENU  # TODO: missing in hikari
