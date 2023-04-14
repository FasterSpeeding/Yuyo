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
# pyright: reportUnusedVariable=none

import uuid

import alluka
import hikari
import tanjun

from yuyo import components


async def callback(ctx: components.Context) -> None:
    await ctx.respond("Hi")


def action_column_of_menus():
    class Column(components.ActionColumnExecutor):
        @components.as_channel_menu
        async def on_channel_menu(self, ctx: components.Context) -> None:
            ctx.selected_channels

        @components.as_select_menu(hikari.ComponentType.ROLE_SELECT_MENU)
        async def on_role_menu(self, ctx: components.Context) -> None:
            ctx.selected_roles

        @components.with_option("op3", "value3")
        @components.with_option("opt2", "value2")
        @components.with_option("opt1", "value1")
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


def action_column_decoratored_menus():
    @components.with_static_text_menu(
        callback,
        options=[
            hikari.impl.SelectOptionBuilder("opt1", "value1"),
            hikari.impl.SelectOptionBuilder("opt2", "value2"),
            hikari.impl.SelectOptionBuilder("opt3", "value3"),
        ],
    )
    @components.with_static_select_menu(hikari.ComponentType.ROLE_SELECT_MENU, callback)
    @components.with_static_channel_menu(callback)
    class Column(components.ActionColumnExecutor):
        ...

    Column.add_static_select_menu(hikari.ComponentType.USER_SELECT_MENU, callback)
    Column.add_static_select_menu(hikari.ComponentType.MENTIONABLE_SELECT_MENU, callback)


# fmt: off
def action_column_menu_methods():
    column = (
        components.ActionColumnExecutor()
        .add_channel_menu(callback)
        .add_select_menu(hikari.ComponentType.ROLE_SELECT_MENU, callback)
        .add_text_menu(callback)
        .add_option("opt1", "value1")
        .add_option("opt2", "value2")
        .add_option("opt3", "value3")
        .parent
        .add_select_menu(hikari.ComponentType.USER_SELECT_MENU, callback)
        .add_select_menu(hikari.ComponentType.MENTIONABLE_SELECT_MENU, callback)
    )
# fmt: on


def action_column_button_methods():
    column = (
        components.ActionColumnExecutor()
        .add_interactive_button(hikari.ButtonStyle.DANGER, callback, label="👍")
        .add_link_button("https://example.com", label="label")
    )


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
        @components.as_interactive_button(hikari.ButtonStyle.DANGER, custom_id="GLOBALLY_UNIQUE", emoji="👍")
        async def on_button(self, ctx: components.Context) -> None:
            session_id = uuid.UUID(ctx.id_metadata)

    column = ColumnCls()

    client = components.ComponentClient()
    client.register_executor(column, timeout=None)

    ...

    async def command_callback(
        ctx: tanjun.abc.AppCommandContext, component_client: alluka.Injected[components.Client]
    ) -> None:
        session_id = uuid.uuid4()
        await ctx.respond(components=ColumnCls(id_metadata={"GLOBALLY_UNIQUE": str(session_id)}).rows)
