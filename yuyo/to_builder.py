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
"""Utility functions for converting Hikari data modals to builders."""
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
import typing
from collections import abc as collections

import hikari


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
        If an unsupported command type is passed.

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
        If an unsupported context menu type is passed.

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

        * [ACTION_ROW][hikari.components.ComponentType.ACTION_ROW]
        * [BUTTON][hikari.components.ComponentType.BUTTON]
        * [TEXT_SELECT_MENU][hikari.components.ComponentType.TEXT_SELECT_MENU]
        * [USER_SELECT_MENU][hikari.components.ComponentType.USER_SELECT_MENU]
        * [ROLE_SELECT_MENU][hikari.components.ComponentType.ROLE_SELECT_MENU]
        * [MENTIONABLE_SELECT_MENU][hikari.components.ComponentType.MENTIONABLE_SELECT_MENU]
        * [CHANNEL_SELECT_MENU][hikari.components.ComponentType.CHANNEL_SELECT_MENU]
    """
    return hikari.impl.MessageActionRowBuilder(
        components=[_to_sub_component(component) for component in action_row.components]
    )


def to_button_builder(
    button: hikari.ButtonComponent, /
) -> typing.Union[hikari.api.LinkButtonBuilder, hikari.api.InteractiveButtonBuilder]:
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
        return hikari.impl.LinkButtonBuilder(url=button.url, label=label, is_disabled=button.is_disabled, emoji=emoji)

    assert button.custom_id is not None
    return hikari.impl.InteractiveButtonBuilder(
        style=button.style, custom_id=button.custom_id, label=label, is_disabled=button.is_disabled, emoji=emoji
    )


def to_channel_select_menu_builder(
    select_menu: hikari.ChannelSelectMenuComponent, /
) -> hikari.api.ChannelSelectMenuBuilder:
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
    return hikari.impl.ChannelSelectMenuBuilder(
        channel_types=[hikari.ChannelType(channel_type) for channel_type in select_menu.channel_types],
        custom_id=select_menu.custom_id,
        placeholder=select_menu.placeholder if select_menu.placeholder is not None else hikari.UNDEFINED,
        min_values=select_menu.min_values,
        max_values=select_menu.max_values,
        is_disabled=select_menu.is_disabled,
    )


def to_text_select_menu_builder(
    select_menu: hikari.TextSelectMenuComponent, /
) -> hikari.api.TextSelectMenuBuilder[typing.Any]:
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
    options = [
        hikari.impl.SelectOptionBuilder(
            label=opt.label,
            value=opt.value,
            description=opt.description if opt.description is not None else hikari.UNDEFINED,
            is_default=opt.is_default,
            emoji=opt.emoji if opt.emoji is not None else hikari.UNDEFINED,
        )
        for opt in select_menu.options
    ]

    return hikari.impl.TextSelectMenuBuilder(
        custom_id=select_menu.custom_id,
        options=options,
        placeholder=select_menu.placeholder if select_menu.placeholder is not None else hikari.UNDEFINED,
        min_values=select_menu.min_values,
        max_values=select_menu.max_values,
        is_disabled=select_menu.is_disabled,
    )


_SELECT_MENU_BUILDERS: dict[int, collections.Callable[[typing.Any], hikari.api.SelectMenuBuilder]] = {
    hikari.ComponentType.CHANNEL_SELECT_MENU: to_channel_select_menu_builder,
    hikari.ComponentType.TEXT_SELECT_MENU: to_text_select_menu_builder,
}


def to_select_menu_builder(select_menu: hikari.SelectMenuComponent, /) -> hikari.api.SelectMenuBuilder:
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
