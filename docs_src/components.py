# -*- coding: utf-8 -*-
# Tanjun Examples - A collection of examples for Tanjun.
# Written in 2023 by Lucina Lucina@lmbyrne.dev
#
# To the extent possible under law, the author(s) have dedicated all copyright
# and related and neighboring rights to this software to the public domain worldwide.
# This software is distributed without any warranty.
#
# You should have received a copy of the CC0 Public Domain Dedication along with this software.
# If not, see <https://creativecommons.org/publicdomain/zero/1.0/>.

import hikari

# pyright: reportUnusedClass=none
from yuyo import components


def action_column_of_menus():
    class Column(components.ActionColumnExecutor):
        __slots__ = ()

        def __init__(self) -> None:
            ...

        @components.as_channel_menu
        async def on_channel_menu(self, ctx: components.Context) -> None:
            ctx.select_channels

        @components.as_select_menu(hikari.ComponentType.ROLE_SELECT_MENU)
        async def on_role_menu(self, ctx: components.Context) -> None:
            ctx.select_roles

        @components.as_text_menu
        async def on_text_menu(self, ctx: components.Context) -> None:
            ctx.select_texts

        @components.as_select_menu(hikari.ComponentType.USER_SELECT_MENU)
        async def on_user_menu(self, ctx: components.Context) -> None:
            ctx.select_users

        @components.as_select_menu(hikari.ComponentType.MENTIONABLE_SELECT_MENU)
        async def on_mentionable_menu(self, ctx: components.Context) -> None:
            ctx.select_roles
            ctx.select_users


def action_column_of_buttons():
    class Column(components.ActionColumnExecutor):
        @components.as_interactive_button(hikari.ButtonStyle.DANGER, emoji="👍")
        async def on_button(self, ctx: components.Context) -> None:
            ...

        link_button = components.link_button("https://example.com", label="label")
