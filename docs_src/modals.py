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

# pyright: reportIncompatibleMethodOverride=none
# pyright: reportUnusedClass=none
# pyright: reportUnusedFunction=none
# pyright: reportUnusedVariable=none
import typing
import uuid

import alluka
import hikari
import tanjun

from yuyo import modals


def modal_class():
    class Modal(modals.Modal):
        async def callback(
            self,
            ctx: modals.Context,
            field: str = modals.text_input("label", min_length=5, max_length=50, default="John Doe"),
            other_field: typing.Optional[str] = modals.text_input(
                "other label", style=hikari.TextInputStyle.PARAGRAPH, default=None
            ),
        ) -> None:
            await ctx.respond("hi")


def modal_class_decorated():
    @modals.with_static_text_input("label", parameter="field", default=None)
    class Modal(modals.Modal):
        async def callback(self, ctx: modals.Context, field: typing.Optional[str], other_field: str) -> None:
            ctx.interaction.components

    Modal.add_static_text_input("other label", parameter="other_field")


def modal_template():
    @modals.with_static_text_input("label", parameter="field", default=None)
    @modals.as_modal_template
    async def modal_template(ctx: modals.Context, field: str, other_field: str = modals.text_input("label")) -> None:
        await ctx.respond("hi")

    modal_template.add_static_text_input("other label")


def decorated_modal():
    @modals.with_text_input("other label", parameter="other")
    @modals.with_text_input("label", parameter="field")
    @modals.as_modal
    async def modal(ctx: modals.Context, field: str, other_field: typing.Optional[str]) -> None:
        ...


def modal_methods():
    async def callback(ctx: modals.Context, field: str, other_field: typing.Optional[str]) -> None:
        ...

    modal = (
        modals.modal(callback)
        .add_text_input("label", parameter="field")
        .add_text_input("other label", parameter="other_field", default=None)
    )


def modal_dataclass():
    class ModalOptions(modals.ModalOptions):
        field: str = modals.text_input("label", min_length=5, max_length=500)
        other_field: typing.Optional[str] = modals.text_input(
            "other label", default=None, style=hikari.TextInputStyle.PARAGRAPH
        )

    @modals.as_modal(parse_signature=True)
    async def modal(ctx: modals.Context, options: ModalOptions) -> None:
        options.field


def creating_a_modal():
    class Modal(modals.Modal):
        __slots__ = ("state",)

        def __init__(self, state: str) -> None:
            self.state = state

        async def modal_template(self, ctx: modals.Context, field: str = modals.text_input("field")) -> None:
            await ctx.respond(self.state)

    async def command_callback(ctx: tanjun.abc.AppCommandContext, modal_client: alluka.Injected[modals.Client]) -> None:
        modal = Modal("state")
        custom_id = str(ctx.interaction.id)
        modal_client.register_modal(custom_id, modal)
        await ctx.create_modal_response("Title", custom_id, components=modal.rows)


def creating_a_static_modal():
    # parse_signature defaults to False for as_modal and modal (unlike as_modal_template).
    @modals.as_modal(parse_signature=True)
    async def modal(ctx: modals.Context, field: str = modals.text_input("field")) -> None:
        session_id = uuid.UUID(ctx.id_metadata)

    MODAL_ID = "MODAL_ID"

    client = modals.ModalClient()
    client.register_modal(MODAL_ID, modal, timeout=None)

    ...

    async def command_callback(
        ctx: tanjun.abc.AppCommandContext, modal_client: alluka.Injected[modals.ModalClient]
    ) -> None:
        session_id = uuid.uuid4()
        await ctx.create_modal_response("Title", f"{MODAL_ID}:{session_id}")
