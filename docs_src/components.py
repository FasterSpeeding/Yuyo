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

# pyright: reportUnusedClass=none
# pyright: reportUnusedFunction=none
import alluka
import hikari
import tanjun

from yuyo import components


def action_column_of_menus():
    class Column(components.ActionColumnExecutor):
        __slots__ = ()

        def __init__(self) -> None:
            ...

        @components.as_channel_menu
        async def on_channel_menu(self, ctx: components.Context) -> None:
            ctx.selected_channels

        @components.as_select_menu(hikari.ComponentType.ROLE_SELECT_MENU)
        async def on_role_menu(self, ctx: components.Context) -> None:
            ctx.selected_roles

        @components.as_text_menu
        async def on_text_menu(self, ctx: components.Context) -> None:
            ctx.selected_texts

        @components.as_select_menu(hikari.ComponentType.USER_SELECT_MENU)
        async def on_user_menu(self, ctx: components.Context) -> None:
            ctx.selected_users

        @components.as_select_menu(hikari.ComponentType.MENTIONABLE_SELECT_MENU)
        async def on_mentionable_menu(self, ctx: components.Context) -> None:
            ctx.selected_roles
            ctx.selected_users


def action_column_of_buttons():
    class Column(components.ActionColumnExecutor):
        @components.as_interactive_button(hikari.ButtonStyle.DANGER, emoji="👍")
        async def on_button(self, ctx: components.Context) -> None:
            ...

        link_button = components.link_button("https://example.com", label="label")


def creating_a_component():
    class ColumnCls(components.ActionColumnExecutor):
        __slots__ = ("state",)

        def __init__(self, state: int) -> None:
            self.state = state

        @components.as_interactive_button(hikari.ButtonStyle.DANGER, emoji="👍")
        async def on_button(self, ctx: components.Context) -> None:
            ...

    async def command_callback(
        ctx: tanjun.abc.AppCommandContext, component_client: alluka.Injected[components.Client]
    ) -> None:
        column = ColumnCls(123)
        message = await ctx.respond(components=column.rows)
        component_client.register_executor(column, message=message)


def creating_a_static_component():
    class ColumnCls(components.ActionColumnExecutor):
        @components.as_interactive_button(hikari.ButtonStyle.DANGER, emoji="👍")
        async def on_button(self, ctx: components.Context) -> None:
            ...

    column = ColumnCls()

    client = components.ComponentClient()
    client.register_executor(column, timeout=None)

    ...

    async def command_callback(
        ctx: tanjun.abc.AppCommandContext, component_client: alluka.Injected[components.Client]
    ) -> None:
        await ctx.respond(components=ColumnCls(id_metadata={}).rows)
