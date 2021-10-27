# -*- coding: utf-8 -*-
# cython: language_level=3
"""General examples how Yuyo's component client is used."""
import hikari

import yuyo

bot = hikari.GatewayBot("TOKEN")
component_client = yuyo.ComponentClient.from_gateway_bot(bot)


async def on_starting(event: hikari.StartingEvent) -> None:
    component_client.open()


async def on_stopping(event: hikari.StoppingEvent) -> None:
    component_client.close()


async def add_paginator(event: hikari.MessageCreateEvent) -> None:
    # ComponentPaginator's takes an iterator of pages to paginate as its first arguments.
    #
    # Under the current implementation each page must be represented by a tuple of
    # (str | UNDEFINED, Embed | UNDEFINED) where str represents the message's content.
    fields = iter(
        [
            ("page 1\nok", hikari.UNDEFINED),
            (hikari.UNDEFINED, hikari.Embed(description="page 2")),
            ("page3\nok", hikari.Embed(description="page3")),
        ]
    )

    # Authors is provided here to whitelist the message's author for paginator access.
    # Alternatively `None` may be passed for authors to leave the paginator public.
    paginator = yuyo.ComponentPaginator(fields, authors=(event.author_id,))
    # Here we use "get_next_entry" to get the first entry to use in the target message for
    # this paginator while also incrementing the paginator's internal index.
    first_page = await paginator.get_next_entry()
    assert first_page, "get_next_entry shouldn't ever return None here as we already know the amount of pages"
    message = await event.message.respond(content=first_page[0], embed=first_page[1])
    component_client.set_executor(message, paginator)
