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

# pyright: reportUnusedExpression=none
# pyright: reportUnusedFunction=none
# pyright: reportUnusedVariable=none
import hikari
import sake

import yuyo


def top_gg(bot: hikari.GatewayBot):
    manager = yuyo.list_status.ServiceManager.from_gateway_bot(bot)
    manager.add_service(yuyo.list_status.TopGGService("TOKEN"))


def discord_bot_list(bot: hikari.GatewayBot):
    manager = yuyo.list_status.ServiceManager.from_gateway_bot(bot)
    manager.add_service(yuyo.list_status.DiscordBotListService("TOKEN"))


def bots_gg(bot: hikari.GatewayBot):
    manager = yuyo.list_status.ServiceManager.from_gateway_bot(bot)
    manager.add_service(yuyo.list_status.BotsGGService("TOKEN"))


def sake_counter(bot: hikari.GatewayBot, cache: sake.abc.GuildCache):
    cache  # type: sake.abc.GuildCache
    counter = yuyo.list_status.SakeStrategy(cache)
    manager = yuyo.list_status.ServiceManager.from_gateway_bot(bot, strategy=counter)


def custom_service(bot: hikari.GatewayBot):
    manager = yuyo.list_status.ServiceManager.from_gateway_bot(bot)

    @manager.with_service()
    async def service(client: yuyo.list_status.AbstractManager, /) -> None:
        count = await client.counter.count()

        if isinstance(count, int):
            ...  # This is a global count of how many guilds the bot is in.

        else:
            # This is a mapping of shard IDs to guild counts.
            count  # type: Mapping[int, int]
