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
    "to_cmd_builder",
    "to_slash_cmd_builder",
    "to_context_menu_builder",
    "to_msg_action_row_builder",
    "to_button_builder",
    "to_select_menu_builder",
]

import copy
import typing
from collections import abc as collections

import hikari

if typing.TYPE_CHECKING:
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

        Currently [hikari.SlashCommand][] and [hikari.ContextMenuCommand][] are supported.
    """
    try:
        builder = _COMMAND_BUILDERS[cmd.type]

    except KeyError:
        raise NotImplementedError(cmd.type) from None

    return builder(_COMMAND_BUILDERS)


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
        name_localizations=cmd.name_localizations,
        description_localizations=cmd.description_localizations,
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

        Currently [hikari.CommandType.MESSAGE][] and
        [hikari.CommandType.USER][] are supported.
    """
    return hikari.impl.ContextMenuCommandBuilder(
        name=cmd.name,
        type=cmd.type,
        id=cmd.id,
        default_member_permissions=cmd.default_member_permissions,
        is_dm_enabled=cmd.is_dm_enabled,
        is_nsfw=cmd.is_nsfw,
        name_localizations=cmd.name_localizations,
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

        * [hikari.ComponentType.ACTION_ROW][]
        * [hikari.ComponentType.BUTTON][]
        * [hikari.ComponentType.SELECT_MENU][]
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
    if button.type is hikari.ButtonStyle.LINK:
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


def to_select_menu_builder(select_menu: hikari.SelectMenuComponent, /) -> hikari.api.SelectMenuBuilder[typing.Any]:
    """Convert a select menu component to a builder.

    Parameters
    ----------
    select_menu
        The selectmenu to convert to a builder.

    Returns
    -------
    hikari.api.SelectMenuBuilder
        The select menu builder.
    """
    return hikari.impl.SelectMenuBuilder(
        container=_DummyContainer(),
        custom_id=select_menu.custom_id,
        options=[],
        placeholder=select_menu.placeholder if select_menu.placeholder is not None else hikari.UNDEFINED,
        min_values=select_menu.min_values,
        max_values=select_menu.max_values,
        is_disabled=select_menu.is_disabled,
    )


_SUB_COMPONENTS: dict[hikari.ComponentType, collections.Callable[[typing.Any], hikari.api.ComponentBuilder]] = {
    hikari.ComponentType.ACTION_ROW: to_msg_action_row_builder,
    hikari.ComponentType.BUTTON: to_button_builder,
    hikari.ComponentType.SELECT_MENU: to_select_menu_builder,
}


def _to_sub_component(component: hikari.PartialComponent, /) -> hikari.api.ComponentBuilder:
    try:
        builder = _SUB_COMPONENTS[hikari.ComponentType(component.type)]

    except KeyError:
        raise NotImplementedError(component.type) from None

    return builder(component)

# TODO: to_message_builder and to_guild_builder
