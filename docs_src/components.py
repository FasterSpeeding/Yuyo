# -*- coding: utf-8 -*-
# Yuyo Examples - A collection of examples for Yuyo.
# Written in 2023 by Faster Speeding Lucina@lmbyrne.dev
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
from collections import abc as collections

import alluka
import hikari
import tanjun

from yuyo import components
from yuyo import pagination


async def callback(ctx: components.Context) -> None:
    await ctx.respond("Hi")


def action_column_of_menus() -> None:
    class Column(components.ActionColumnExecutor):
        @components.as_channel_menu
        async def on_channel_menu(self, ctx: components.Context) -> None:
            ctx.selected_channels

        @components.as_role_menu
        async def on_role_menu(self, ctx: components.Context) -> None:
            ctx.selected_roles

        @components.with_option("opt3", "value3")
        @components.with_option("opt2", "value2")
        @components.with_option("opt1", "value1")
        @components.as_text_menu
        async def on_text_menu(self, ctx: components.Context) -> None:
            ctx.selected_texts

        @components.as_user_menu
        async def on_user_menu(self, ctx: components.Context) -> None:
            ctx.selected_users

        @components.as_mentionable_menu
        async def on_mentionable_menu(self, ctx: components.Context) -> None:
            ctx.selected_roles
            ctx.selected_users


def action_column_of_buttons() -> None:
    class Column(components.ActionColumnExecutor):
        @components.as_interactive_button(hikari.ButtonStyle.DANGER, emoji="👍")
        async def on_button(self, ctx: components.Context) -> None:
            ...

        link_button = components.link_button("https://example.com", label="label")


# fmt: off
def column_template_builder() -> None:
    column_template = (
        components.column_template()
        .add_static_channel_menu(callback)
        .add_static_text_menu(callback)
        .add_option("opt1", "value1")
        .add_option("opt2", "value2")
        .add_option("opt3", "value3")
        .parent
        .add_static_role_menu(callback)
        .add_static_link_button("https://example.com")
        .add_static_interactive_button(hikari.ButtonStyle.DANGER, callback, label="👍")
    )
# fmt: on


def column_template_decorator_methods() -> None:
    column_template = components.column_template()

    @column_template.with_static_channel_menu
    async def on_channel_menu(ctx: components.Context) -> None:
        ...

    @components.with_option("opt3", "value3")
    @components.with_option("opt2", "value2")
    @components.with_option("opt1", "value1")
    @column_template.with_static_text_menu
    async def on_text_menu(ctx: components.Context) -> None:
        ...

    @column_template.with_static_role_menu
    async def on_role_menu(ctx: components.Context) -> None:
        ...

    @column_template.with_static_interactive_button(hikari.ButtonStyle.DANGER, label="👍")
    async def on_button(ctx: components.Context) -> None:
        ...


# fmt: off
def action_column_menu_methods() -> None:
    column = (
        components.ActionColumnExecutor()
        .add_channel_menu(callback)
        .add_text_menu(callback)
        .add_option("opt1", "value1")
        .add_option("opt2", "value2")
        .add_option("opt3", "value3")
        .parent
        .add_role_menu(callback)
        .add_link_button("https://example.com", label="label")
        .add_interactive_button(hikari.ButtonStyle.DANGER, callback, label="👍")
    )
# fmt: on


def action_column_with_methods() -> None:
    column = components.ActionColumnExecutor()

    @column.with_channel_menu
    async def on_channel_menu(ctx: components.Context) -> None:
        ...

    @components.with_option("opt3", "value3")
    @components.with_option("opt2", "value2")
    @components.with_option("opt1", "value1")
    @column.with_text_menu
    async def on_text_menu(ctx: components.Context) -> None:
        ...

    @column.with_role_menu
    async def on_role_menu(ctx: components.Context) -> None:
        ...

    @column.with_interactive_button(hikari.ButtonStyle.DANGER, label="👍")
    async def on_button(ctx: components.Context) -> None:
        ...


def creating_a_component() -> None:
    class ColumnCls(components.ActionColumnExecutor):
        __slots__ = ("state",)

        def __init__(self, state: int) -> None:
            super().__init__()
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


def creating_a_static_component() -> None:
    class ColumnCls(components.ActionColumnExecutor):
        @components.as_interactive_button(hikari.ButtonStyle.DANGER, emoji="👍")
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
        await ctx.respond(components=ColumnCls(id_metadata={"on_button": str(session_id)}).rows)


def create_response() -> None:
    class ColumnCls(components.ActionColumnExecutor):
        @components.as_interactive_button(hikari.ButtonStyle.DANGER, emoji="👍")
        async def on_button(self, ctx: components.Context) -> None:
            await ctx.respond(
                "Message content",
                attachments=[hikari.URL("https://img3.gelbooru.com/images/40/5a/405ad89e26a8ec0e96fd09dd1ade334b.jpg")],
            )


def ephemeral_response() -> None:
    class ColumnCls(components.ActionColumnExecutor):
        @components.as_interactive_button(hikari.ButtonStyle.DANGER, emoji="👍")
        async def on_button(self, ctx: components.Context) -> None:
            await ctx.create_initial_response("Starting cat", ephemeral=True)
            await ctx.create_followup("The cat rules us all now", ephemeral=True)


def updating_source() -> None:
    class ColumnCls(components.ActionColumnExecutor):
        @components.as_interactive_button(hikari.ButtonStyle.DANGER, emoji="👍")
        async def on_button(self, ctx: components.Context) -> None:
            await ctx.create_initial_response(response_type=hikari.ResponseType.MESSAGE_UPDATE, attachments=[])


def paginator_example() -> None:
    async def command(ctx: tanjun.abc.Context, component_client: alluka.Injected[components.Client]) -> None:
        pages = [pagination.Page("Page 1"), pagination.Page("Page 2"), pagination.Page("Page 3")]
        paginator = components.Paginator(iter(pages))

        message = await ctx.respond(components=paginator.rows, ensure_result=True)
        component_client.register_executor(paginator, message=message)


async def _async_iterator() -> collections.AsyncIterator[str]:
    yield "meow"


def async_paginator_example(bot: hikari.GatewayBot) -> None:
    pages = (pagination.Page(content) async for content in _async_iterator())
    paginator = components.Paginator(pages)


def all_buttons(pages: collections.Iterator[pagination.Page]) -> None:
    paginator = (
        components.Paginator(pages, triggers=[])
        .add_first_button()
        .add_previous_button()
        .add_stop_button()
        .add_next_button()
        .add_last_button()
    )


def wait_for_example() -> None:
    ...


def stream_example() -> None:
    ...
