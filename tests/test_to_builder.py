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

import typing
from unittest import mock

import hikari
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
    result = yuyo.to_cmd_builder(
        mock.Mock(type=cmd_type, name_localizations={}, description_localizations={}, options=[])
    )

    assert isinstance(result, expected_cls)


def test_to_cmd_builder_with_unknown_cmd_type():
    mock_cmd = mock.Mock(type=123321123)

    with pytest.raises(NotImplementedError, match="123321123"):
        yuyo.to_cmd_builder(mock_cmd)


def test_to_slash_cmd_builder():
    mock_slash_cmd = typing.cast(
        hikari.SlashCommand,
        mock.Mock(
            options=None,
            name_localizations={hikari.Locale.BG: "sa", hikari.Locale.PT_BR: "42342sdsaasd"},
            description_localizations={hikari.Locale.DE: "dsjjqwe", hikari.Locale: "roikweioji"},
        ),
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
    mock_option_1 = typing.cast(
        hikari.CommandOption,
        mock.Mock(
            description_localizations={hikari.Locale.JA: "jajaja"},
            channel_types=[hikari.ChannelType.GUILD_FORUM, hikari.ChannelType.GUILD_NEWS_THREAD],
            choices=[hikari.CommandChoice(name="hi", value="bye"), hikari.CommandChoice(name="x", value="d")],
            name_localizations={hikari.Locale.FI: "finished", hikari.Locale.BG: "background"},
            options=None,
        ),
    )
    mock_option_2 = typing.cast(
        hikari.CommandOption,
        mock.Mock(
            description_localizations={hikari.Locale.HR: "sheeeeeeeeeeeeeeeeeeeeeeeeeeeeeeera"},
            channel_types=None,
            choices=None,
            name_localizations={hikari.Locale.CS: "Cope"},
            options=None,
        ),
    )
    mock_slash_cmd = typing.cast(
        hikari.SlashCommand,
        mock.Mock(options=[mock_option_1, mock_option_2], name_localizations={}, description_localizations={}),
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
    mock_option_1 = typing.cast(
        hikari.CommandOption,
        mock.Mock(
            description_localizations={hikari.Locale.JA: "jajaja"},
            channel_types=[hikari.ChannelType.GUILD_FORUM, hikari.ChannelType.GUILD_NEWS_THREAD],
            choices=[hikari.CommandChoice(name="hi", value="bye"), hikari.CommandChoice(name="x", value="d")],
            name_localizations={hikari.Locale.FI: "finished", hikari.Locale.BG: "background"},
            options=None,
        ),
    )
    mock_option_2 = typing.cast(
        hikari.CommandOption,
        mock.Mock(
            description_localizations={hikari.Locale.HR: "sheeeeeeeeeeeeeeeeeeeeeeeeeeeeeeera"},
            channel_types=None,
            choices=None,
            name_localizations={hikari.Locale.CS: "Cope"},
            options=None,
        ),
    )
    mock_cmd_option = mock.Mock(
        description_localizations={},
        channel_types=None,
        choices=None,
        name_localizations={},
        options=[mock_option_1, mock_option_2],
    )
    mock_slash_cmd = typing.cast(
        hikari.SlashCommand, mock.Mock(options=[mock_cmd_option], name_localizations={}, description_localizations={})
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
    mock_option_1 = typing.cast(
        hikari.CommandOption,
        mock.Mock(
            description_localizations={hikari.Locale.JA: "jajaja"},
            channel_types=[hikari.ChannelType.GUILD_FORUM, hikari.ChannelType.GUILD_NEWS_THREAD],
            choices=[hikari.CommandChoice(name="hi", value="bye"), hikari.CommandChoice(name="x", value="d")],
            name_localizations={hikari.Locale.FI: "finished", hikari.Locale.BG: "background"},
            options=None,
        ),
    )
    mock_option_2 = typing.cast(
        hikari.CommandOption,
        mock.Mock(
            description_localizations={hikari.Locale.HR: "sheeeeeeeeeeeeeeeeeeeeeeeeeeeeeeera"},
            channel_types=None,
            choices=None,
            name_localizations={hikari.Locale.CS: "Cope"},
            options=None,
        ),
    )
    mock_nested_cmd_option = mock.Mock(
        description_localizations={},
        channel_types=None,
        choices=None,
        name_localizations={},
        options=[mock_option_1, mock_option_2],
    )
    mock_cmd_option = mock.Mock(
        description_localizations={},
        channel_types=None,
        choices=None,
        name_localizations={},
        options=[mock_nested_cmd_option],
    )
    mock_slash_cmd = typing.cast(
        hikari.SlashCommand, mock.Mock(options=[mock_cmd_option], name_localizations={}, description_localizations={})
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
    mock_cmd = typing.cast(
        hikari.ContextMenuCommand,
        mock.Mock(
            hikari.ContextMenuCommand, name_localizations={hikari.Locale.CS: "gasdas", hikari.Locale.DE: "hgfdasd"}
        ),
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


@pytest.mark.skip(reason="TODO")
def test_to_msg_action_row_builder():
    ...


def test_to_button_builder_for_link_button():
    mock_button = typing.cast(
        hikari.ButtonComponent, mock.Mock(custom_id=None, emoji=None, label=None, style=hikari.ButtonStyle.LINK)
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.LinkButtonBuilder)
    assert result.style is hikari.ButtonStyle.LINK
    assert result.url is mock_button.url
    assert result.label is hikari.UNDEFINED
    assert result.emoji is hikari.UNDEFINED
    assert "emoji" not in result.build()


def test_to_button_builder_for_link_button_when_all_fields_set():
    mock_button = typing.cast(
        hikari.ButtonComponent,
        mock.Mock(
            custom_id=None,
            emoji=hikari.CustomEmoji(id=hikari.Snowflake(65234), name="kon'nichiwa", is_animated=True),
            style=hikari.ButtonStyle.LINK,
        ),
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.LinkButtonBuilder)
    assert result.style is hikari.ButtonStyle.LINK
    assert result.url is mock_button.url
    assert result.label is mock_button.label
    assert result.emoji is mock_button.emoji
    assert result.build()["emoji"] == {"id": "65234"}


def test_to_button_builder_for_link_button_when_emoji_is_custom():
    mock_button = typing.cast(
        hikari.ButtonComponent,
        mock.Mock(custom_id=None, emoji=hikari.UnicodeEmoji("bin"), style=hikari.ButtonStyle.LINK),
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.LinkButtonBuilder)
    assert result.emoji is mock_button.emoji
    assert result.build()["emoji"] == {"name": "bin"}


@pytest.mark.parametrize("button_style", set(hikari.ButtonStyle).difference({hikari.ButtonStyle.LINK}))
def test_to_button_builder_for_inactavtive_button(button_style: hikari.ButtonStyle):
    mock_button = typing.cast(hikari.ButtonComponent, mock.Mock(emoji=None, label=None, style=button_style, url=None))

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.InteractiveButtonBuilder)
    assert result.style is button_style
    assert result.custom_id is mock_button.custom_id
    assert result.label is hikari.UNDEFINED
    assert result.is_disabled is mock_button.is_disabled
    assert result.emoji is hikari.UNDEFINED
    assert "emoji" not in result.build()


def test_to_button_builder_for_inactavtive_button_when_all_fields_set():
    mock_button = typing.cast(
        hikari.ButtonComponent,
        mock.Mock(
            emoji=hikari.CustomEmoji(id=hikari.Snowflake(123321), name="hi", is_animated=True),
            style=hikari.ButtonStyle.PRIMARY,
            url=None,
        ),
    )

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.InteractiveButtonBuilder)
    assert result.style is mock_button.style
    assert result.custom_id is mock_button.custom_id
    assert result.label is mock_button.label
    assert result.is_disabled is mock_button.is_disabled
    assert result.emoji is mock_button.emoji
    assert result.build()["emoji"] == {"id": "123321"}


@pytest.mark.parametrize("emoji", ["hi", hikari.UnicodeEmoji("meow")])
def test_to_button_builder_for_inactavtive_button_when_emoji_is_custom(emoji: str):
    mock_button = typing.cast(hikari.ButtonComponent, mock.Mock(emoji=emoji, style=hikari.ButtonStyle.SECONDARY))

    result = yuyo.to_builder.to_button_builder(mock_button)

    assert isinstance(result, hikari.api.InteractiveButtonBuilder)
    assert result.emoji is mock_button.emoji
    assert result.build()["emoji"] == {"name": emoji}


@pytest.mark.skip(reason="TODO")
def test_to_select_menu_builder():
    ...


@pytest.mark.skip(reason="TODO")
def test_to_select_menu_builder_when_sub_type_unknown():
    ...
