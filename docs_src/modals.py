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
import typing

import hikari

from yuyo import modals


def modal_class():
    class Modal(modals.Modal):
        __slots__ = ("_response",)

        def __init__(self, response: str) -> None:
            self._response = response

        async def callback(self, ctx: modals.Context) -> None:
            await ctx.respond(self._response)


def modal_class_fields():
    class Modal(modals.Modal):
        async def callback(
            self,
            ctx: modals.Context,
            field: str = modals.text_input("label"),
            other_field: typing.Optional[str] = modals.text_input("label"),
        ) -> None:
            await ctx.respond("hi")


def modal_template_fields():
    async def modal_template(ctx: modals.Context, field: str = modals.text_input("label")) -> None:
        await ctx.respond("hi")


def modal_template_dataclass():
    class ModalOptions(modals.ModalOptions):
        field: str = modals.text_input("label", min_length=5, max_length=500)
        other_field: typing.Optional[str] = modals.text_input(
            "label", default=None, style=hikari.TextInputStyle.PARAGRAPH
        )

    @modals.as_modal_template
    async def modal_template(ctx: modals.ModalContext, options: ModalOptions) -> None:
        ...
