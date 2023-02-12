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
"""Utility functions for converting Hikari data models to builders."""
from __future__ import annotations

__all__: list[str] = [
    "to_button_builder",
    "to_cmd_builder",
    "to_context_menu_builder",
    "to_msg_action_row_builder",
    "to_select_menu_builder",
    "to_slash_cmd_builder",
]

import copy
import dataclasses
import typing
from collections import abc as collections

import hikari
import hikari.components  # TODO: import temporarily needed due to hikari not exporting TL.
import hikari.impl.special_endpoints  # TODO: import temporarily needed to missing impl exports.

if typing.TYPE_CHECKING:
    import hikari.api  # TODO: import temporarily needed to missing api exports.
    import hikari.api.special_endpoints  # TODO: import temporarily needed to missing impl exports.
    import hikari.impl  # TODO: import temporarily needed to missing impl exports.
    from typing_extensions import Self


def to_cmd_builder(cmd: hikari.PartialCommand, /) -> hikari.api.CommandBuilder:
    """Convert a partial command to a command builder.

    Parameters
    ----------
    cmd
        The command to convert to a builder.

    Returns
    -------
    hikari.api.CommandBuilder
        The command builder.

        This will always be a subclass.

    Raises
    ------
    NotImplementedError
        If a unsupported command type is passed.

        Currently [hikari.commands.SlashCommand][] and
        [hikari.commands.ContextMenuCommand][] are supported.
    """
    try:
        builder = _COMMAND_BUILDERS[cmd.type]

    except KeyError:
        raise NotImplementedError(cmd.type) from None

    return builder(cmd)


def _to_cmd_opt(option: hikari.CommandOption, /) -> hikari.CommandOption:
    choices = [copy.copy(choice) for choice in option.choices] if option.choices is not None else None
    options = [_to_cmd_opt(opt) for opt in option.options] if option.options is not None else None

    return hikari.CommandOption(
        type=option.type,
        name=option.name,
        description=option.description,
        is_required=option.is_required,
        choices=choices,
        options=options,
        channel_types=list(option.channel_types) if option.channel_types is not None else None,
        autocomplete=option.autocomplete,
        min_value=option.min_value,
        max_value=option.max_value,
        name_localizations=dict(option.name_localizations),
        description_localizations=dict(option.description_localizations),
        min_length=option.min_length,
        max_length=option.max_length,
    )


def to_slash_cmd_builder(cmd: hikari.SlashCommand, /) -> hikari.api.SlashCommandBuilder:
    """Convert a slash command to a builder.

    Parameters
    ----------
    cmd
        The command to convert to a builder.

    Returns
    -------
    hikari.api.SlashCommandBuilder
        The slash command builder.
    """
    return hikari.impl.SlashCommandBuilder(
        name=cmd.name,
        description=cmd.description,
        options=[_to_cmd_opt(opt) for opt in cmd.options or ()],
        id=cmd.id,
        default_member_permissions=cmd.default_member_permissions,
        is_dm_enabled=cmd.is_dm_enabled,
        is_nsfw=cmd.is_nsfw,
        name_localizations=dict(cmd.name_localizations),
        description_localizations=dict(cmd.description_localizations),
    )


def to_context_menu_builder(cmd: hikari.ContextMenuCommand, /) -> hikari.api.ContextMenuCommandBuilder:
    """Convert a context menu command to a builder.

    Parameters
    ----------
    cmd
        The context menu command to convert to a builder.

    Returns
    -------
    hikari.api.ContextMenuCommandBuilder
        The context menu command builder.

    Raises
    ------
    NotImplementedError
        If a unsupported context menu type is passed.

        Currently [hikari.commands.CommandType.MESSAGE][] and
        [hikari.commands.CommandType.USER][] are supported.
    """
    return hikari.impl.ContextMenuCommandBuilder(
        name=cmd.name,
        type=cmd.type,
        id=cmd.id,
        default_member_permissions=cmd.default_member_permissions,
        is_dm_enabled=cmd.is_dm_enabled,
        is_nsfw=cmd.is_nsfw,
        name_localizations=dict(cmd.name_localizations),
    )


_COMMAND_BUILDERS: dict[hikari.CommandType, collections.Callable[[typing.Any], hikari.api.CommandBuilder]] = {
    hikari.CommandType.MESSAGE: to_context_menu_builder,
    hikari.CommandType.SLASH: to_slash_cmd_builder,
    hikari.CommandType.USER: to_context_menu_builder,
}


def to_msg_action_row_builder(action_row: hikari.MessageActionRowComponent, /) -> hikari.api.MessageActionRowBuilder:
    """Convert a message action row component to a builder.

    Parameters
    ----------
    action_row
        The message action row to convert to a builder.

    Returns
    -------
    hikari.api.MessageActionRowBuilder
        The message action row builder.

    Raises
    ------
    NotImplementedError
        If the action row contains an unsupported component type.

        The following are currently supported:

        * [hikari.components.ComponentType.ACTION_ROW][]
        * [hikari.components.ComponentType.BUTTON][]
        * [hikari.components.ComponentType.TEXT_SELECT_MENU][]
        * [hikari.components.ComponentType.USER_SELECT_MENU][]
        * [hikari.components.ComponentType.ROLE_SELECT_MENU][]
        * [hikari.components.ComponentType.MENTIONABLE_SELECT_MENU][]
        * [hikari.components.ComponentType.CHANNEL_SELECT_MENU][]
    """
    return hikari.impl.MessageActionRowBuilder(
        components=[_to_sub_component(component) for component in action_row.components]
    )


class _DummyContainer:
    __slots__ = ()

    def add_component(self, _: hikari.api.ComponentBuilder, /) -> Self:
        raise NotImplementedError("Add to component not supported")


def to_button_builder(
    button: hikari.ButtonComponent, /
) -> typing.Union[hikari.api.LinkButtonBuilder[typing.Any], hikari.api.InteractiveButtonBuilder[typing.Any]]:
    """Convert a button component to a builder.

    Parameters
    ----------
    button
        The button component to convert to a builder.

    Returns
    -------
    hikari.api.LinkButtonBuilder | hikari.api.InteractiveButtonBuilder
        The buttion builder.
    """
    emoji = button.emoji if button.emoji is not None else hikari.UNDEFINED
    label = button.label if button.label is not None else hikari.UNDEFINED
    if button.style is hikari.ButtonStyle.LINK:
        assert button.url is not None
        return hikari.impl.LinkButtonBuilder(
            container=_DummyContainer(), style=button.style, url=button.url, label=label, is_disabled=button.is_disabled
        ).set_emoji(emoji)

    assert button.custom_id is not None
    return hikari.impl.InteractiveButtonBuilder[typing.Any](
        container=_DummyContainer(),
        style=button.style,
        custom_id=button.custom_id,
        label=label,
        is_disabled=button.is_disabled,
    ).set_emoji(emoji)


@dataclasses.dataclass()
class _SelectOptionBuilder(hikari.api.SelectOptionBuilder[typing.Any]):
    """Builder class for select menu options."""

    __slots__ = ("_label", "_value", "_description", "_is_default", "_emoji", "_emoji_id", "_emoji_name")

    _label: str
    _value: str
    _description: hikari.UndefinedOr[str]
    _is_default: bool
    _emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType]
    _emoji_id: hikari.UndefinedOr[str]
    _emoji_name: hikari.UndefinedOr[str]

    @property
    def label(self) -> str:
        return self._label

    @property
    def value(self) -> str:
        return self._value

    @property
    def description(self) -> hikari.UndefinedOr[str]:
        return self._description

    @property
    def emoji(self) -> typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType]:
        return self._emoji

    @property
    def is_default(self) -> bool:
        return self._is_default

    def set_description(self, value: hikari.UndefinedOr[str], /) -> Self:
        self._description = value
        return self

    def set_emoji(self, emoji: typing.Union[hikari.Snowflakeish, hikari.Emoji, str, hikari.UndefinedType], /) -> Self:
        self._emoji = emoji
        self._emoji_id = hikari.UNDEFINED
        self._emoji_name = hikari.UNDEFINED

        if emoji is not hikari.UNDEFINED:
            if isinstance(emoji, (int, hikari.CustomEmoji)):
                self._emoji_id = str(int(emoji))

            self._emoji_name = str(emoji)

        return self

    def set_is_default(self, state: bool, /) -> Self:
        self._is_default = state
        return self

    def add_to_menu(self) -> typing.NoReturn:
        raise NotImplementedError("Add to menu not supported")

    def build(self) -> collections.MutableMapping[str, typing.Any]:
        data: dict[str, typing.Union[str, bool, int, dict[str, typing.Union[str, int]]]] = {}

        data["label"] = self._label
        data["value"] = self._value
        data["default"] = self._is_default

        if self._description is not hikari.UNDEFINED:
            data["description"] = self._description

        if self._emoji_id is not hikari.UNDEFINED:
            data["emoji"] = {"id": self._emoji_id}

        elif self._emoji_name is not hikari.UNDEFINED:
            data["emoji"] = {"name": self._emoji_name}

        return data


def to_channel_select_menu_builder(
    select_menu: hikari.components.ChannelSelectMenuComponent, /
) -> hikari.api.special_endpoints.ChannelSelectMenuBuilder[typing.Any]:
    """Convert a channel select menu component to a builder.

    Parameters
    ----------
    select_menu
        The select menu to convert to a builder.

    Returns
    -------
    hikari.api.ChannelSelectMenuBuilder
        The select menu builder.
    """
    return hikari.impl.special_endpoints.ChannelSelectMenuBuilder(
        channel_types=[hikari.ChannelType(channel_type) for channel_type in select_menu.channel_types],
        container=_DummyContainer(),
        custom_id=select_menu.custom_id,
        placeholder=select_menu.placeholder if select_menu.placeholder is not None else hikari.UNDEFINED,
        min_values=select_menu.min_values,
        max_values=select_menu.max_values,
        is_disabled=select_menu.is_disabled,
    )


def to_text_select_menu_builder(
    select_menu: hikari.components.TextSelectMenuComponent, /
) -> hikari.api.special_endpoints.TextSelectMenuBuilder[typing.Any]:
    """Convert a text select menu component to a builder.

    Parameters
    ----------
    select_menu
        The select menu to convert to a builder.

    Returns
    -------
    hikari.api.TextSelectMenuBuilder
        The select menu builder.
    """
    options: list[hikari.api.SelectOptionBuilder[typing.Any]] = [
        _SelectOptionBuilder(
            _label=opt.label,
            _value=opt.value,
            _description=opt.description if opt.description is not None else hikari.UNDEFINED,
            _is_default=opt.is_default,
            _emoji=hikari.UNDEFINED,
            _emoji_id=hikari.UNDEFINED,
            _emoji_name=hikari.UNDEFINED,
        ).set_emoji(opt.emoji or hikari.UNDEFINED)
        for opt in select_menu.options
    ]

    return hikari.impl.special_endpoints.TextSelectMenuBuilder(
        container=_DummyContainer(),
        custom_id=select_menu.custom_id,
        options=options,
        placeholder=select_menu.placeholder if select_menu.placeholder is not None else hikari.UNDEFINED,
        min_values=select_menu.min_values,
        max_values=select_menu.max_values,
        is_disabled=select_menu.is_disabled,
    )


_SELECT_MENU_BUILDERS: dict[int, collections.Callable[[typing.Any], hikari.api.SelectMenuBuilder[typing.Any]]] = {
    hikari.ComponentType.CHANNEL_SELECT_MENU: to_channel_select_menu_builder,
    hikari.ComponentType.TEXT_SELECT_MENU: to_text_select_menu_builder,
}


def to_select_menu_builder(select_menu: hikari.SelectMenuComponent, /) -> hikari.api.SelectMenuBuilder[typing.Any]:
    """Convert a select menu component to a builder.

    Parameters
    ----------
    select_menu
        The select menu to convert to a builder.

    Returns
    -------
    hikari.api.SelectMenuBuilder
        The select menu builder.
    """
    if cast := _SELECT_MENU_BUILDERS.get(select_menu.type):
        return cast(select_menu)

    return hikari.impl.SelectMenuBuilder(
        container=_DummyContainer(),
        custom_id=select_menu.custom_id,
        type=select_menu.type,
        placeholder=select_menu.placeholder if select_menu.placeholder is not None else hikari.UNDEFINED,
        min_values=select_menu.min_values,
        max_values=select_menu.max_values,
        is_disabled=select_menu.is_disabled,
    )


_SUB_COMPONENTS: dict[int, collections.Callable[[typing.Any], hikari.api.ComponentBuilder]] = {
    hikari.ComponentType.BUTTON: to_button_builder,
    **_SELECT_MENU_BUILDERS,
    hikari.ComponentType.USER_SELECT_MENU: to_select_menu_builder,
    hikari.ComponentType.ROLE_SELECT_MENU: to_select_menu_builder,
    hikari.ComponentType.MENTIONABLE_SELECT_MENU: to_select_menu_builder,
}


def _to_sub_component(component: hikari.PartialComponent, /) -> hikari.api.ComponentBuilder:
    try:
        builder = _SUB_COMPONENTS[hikari.ComponentType(component.type)]

    except KeyError:
        raise NotImplementedError(component.type) from None

    return builder(component)
