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

# pyright: reportUnusedVariable=none
import os

import agraffe  # type: ignore  # TODO: add py.typed to agraffe
import fastapi  # type: ignore
import tanjun

import yuyo


def make_asgi_bot() -> None:
    rest_bot = yuyo.asgi.AsgiBot(os.environ["TOKEN"])
    tanjun.Client.from_rest_bot(rest_bot)

    # ... more setup


def fastapi_mount() -> None:
    bot = yuyo.asgi.AsgiBot(os.environ["TOKEN"], asgi_managed=False)

    app = fastapi.FastAPI(on_startup=[bot.start], on_shutdown=[bot.close])

    app.mount("/bot", bot)


def serverless() -> None:
    bot = yuyo.AsgiBot(os.environ["TOKEN"].strip(), "Bot")

    # ... Setup bot

    entry_point = agraffe.Agraffe(bot)
