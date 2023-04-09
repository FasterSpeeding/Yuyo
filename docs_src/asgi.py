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
import os

import tanjun

import yuyo

bot = yuyo.asgi.AsgiBot(os.environ["TOKEN"], asgi_managed=False)
tanjun.Client.from_rest_bot(bot)

# ... more setup

import fastapi

app = fastapi.FastAPI(on_startup=[bot.start], on_shutdown=[bot.close])

app.mount("/bot", bot)
