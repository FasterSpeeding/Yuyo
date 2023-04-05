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

# pyright: reportUnusedVariable=none
# pyright: reportUnusedExpression=none
import hikari

import yuyo


def from_link(app: hikari.RESTAware):
    link = yuyo.links.TemplateLink.from_link(app, "https://discord.new/aaaaaaaaaa")


async def find(app: hikari.RESTAware):
    if link := yuyo.links.InviteLink.find(app, "meow you can nyaa us at discord.gg/nekosmeowers"):
        ...


def find_iter(app: hikari.RESTAware):
    for link in yuyo.links.MessageLink.find_iter(app, "message content"):
        ...


async def invite_link(app: hikari.RESTAware):
    link = yuyo.links.InviteLink.from_link(app, "https://discord.gg/nekosmeowers")

    link.code  # == "nekosmeowers"
    await link.fetch()  # hikari.Invite
    link.get()  # hikari.InviteWithMetadata | None
    str(link)  # "https://discord.gg/nekosmeowers"


def make_invite_link():
    link = yuyo.links.make_invite_link("codecode")
    link  # "https://discord.gg/codecode"


async def message_link(app: hikari.RESTAware):
    link = yuyo.links.MessageLink.from_link(
        app, "https://discord.com/channels/54123123321123/2134432234342/56445234124"
    )

    link.is_dm_link  # == False
    link.guild_id  # == 54123123321123
    link.channel_id  # == 2134432234342
    link.message_id  # == 56445234124
    await link.fetch()  # hikari.Message
    link.get()  # hikari.Message | None
    str(link)  # "https://discord.com/channels/54123123321123/2134432234342/56445234124"


def make_message_link():
    #                                  (channel_id, message_id)
    link = yuyo.links.make_message_link(654323412, 4534512332, guild=123321)
    # link = # "https://discord.com/channels/123321/654323412/4534512332"
    link = yuyo.links.make_message_link(333333333, 5555555555)
    # link = # "https://discord.com/channels/@me/333333333/5555555555"


async def template_link(app: hikari.RESTAware):
    link = yuyo.links.TemplateLink.from_link(app, "https://discord.new/aaaaaaaaaa")

    link.code  # == "aaaaaaaaaa"
    await link.fetch()  # hikari.Template
    str(link)  # == "https://discord.new/aaaaaaaaaa"


def make_template_link():
    raw_link = yuyo.links.make_template_link("cododododoe")
    raw_link  # == "https://discord.new/aaaaaaaaaa"


async def webhook_link(app: hikari.RESTAware):
    link = yuyo.links.WebhookLink.from_link(app, "https://discord.com/api/webhooks/123321123/efsdfasdsa")

    link.webhook_id  # == 123321123
    link.token  # == "efsdfasdsa"
    await link.fetch()  # hikari.IncomingWebhook
    str(link)  # == "https://discord.com/api/webhooks/123321123/efsdfasdsa"


def make_webhook_link():
    raw_link = yuyo.links.make_webhook_link(123321, "hfdssdasd")
    raw_link  # == "https://discord.com/api/webhooks/123321123/efsdfasdsa"
