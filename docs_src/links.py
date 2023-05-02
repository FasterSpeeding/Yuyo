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

# pyright: reportUnusedExpression=none
# pyright: reportUnusedVariable=none
import hikari

from yuyo import links


def from_link(app: hikari.RESTAware):
    link = links.TemplateLink.from_link(app, "https://discord.new/aaaaaaaaaa")


async def find(app: hikari.RESTAware):
    if link := links.InviteLink.find(app, "meow you can nyaa us at discord.gg/nekosmeowers"):
        ...


def find_iter(app: hikari.RESTAware):
    for link in links.MessageLink.find_iter(app, "message content"):
        ...


async def channel_link(app: hikari.RESTAware):
    link = links.ChannelLink.from_link(app, "https://discord.com/channels/453123/67765564")

    link.is_dm_link  # value: False
    link.guild_id  # value: 453123
    link.channel_id  # value: 67765564
    await link.fetch_channel()  # type: hikari.PartialChannel
    link.get_channel()  # type: hikari.GuildChannel | None
    await link.fetch_guild()  # type: hikari.RESTGuild | None
    link.get_guild()  # type: hikari.GatewayGuild | None
    str(link)  # value: "https://discord.com/channels/453123/67765564"


def make_channel_link() -> None:
    link = links.make_channel_link(123312, guild=6534234)
    link  # value: "https://discord.com/channels/6534234/123312"
    link = links.make_channel_link(543123)
    link  # value: "https://discord.com/channels/@me/543123"


async def invite_link(app: hikari.RESTAware):
    link = links.InviteLink.from_link(app, "https://discord.gg/nekosmeowers")

    link.code  # value: "nekosmeowers"
    await link.fetch_invite()  # type: hikari.Invite
    link.get_invite()  # type: hikari.InviteWithMetadata | None
    str(link)  # value: "https://discord.gg/nekosmeowers"


def make_invite_link() -> None:
    link = links.make_invite_link("codecode")
    link  # value: "https://discord.gg/codecode"


async def message_link(app: hikari.RESTAware):
    link = links.MessageLink.from_link(app, "https://discord.com/channels/54123123321123/2134432234342/56445234124")

    link.is_dm_link  # value: False
    link.guild_id  # value: 54123123321123
    link.channel_id  # value: 2134432234342
    link.message_id  # value: 56445234124
    await link.fetch_message()  # type: hikari.Message
    link.get_message()  # type: hikari.Message | None
    await link.fetch_channel()  # type: hikari.PartialChannel
    link.get_channel()  # type: hikari.GuildChannel | None
    await link.fetch_guild()  # type: hikari.RESTGuild | None
    link.get_guild()  # type: hikari.GatewayGuild | None
    str(link)  # value: "https://discord.com/channels/54123123321123/2134432234342/56445234124"


def make_message_link() -> None:
    #                             (channel_id, message_id)
    link = links.make_message_link(654323412, 4534512332, guild=123321)
    link  # value: "https://discord.com/channels/123321/654323412/4534512332"
    link = links.make_message_link(333333333, 5555555555)
    link  # value: "https://discord.com/channels/@me/333333333/5555555555"


async def template_link(app: hikari.RESTAware):
    link = links.TemplateLink.from_link(app, "https://discord.new/aaaaaaaaaa")

    link.code  # value: "aaaaaaaaaa"
    await link.fetch_template()  # type: hikari.Template
    str(link)  # value: "https://discord.new/aaaaaaaaaa"


def make_template_link() -> None:
    raw_link = links.make_template_link("cododododoe")
    raw_link  # value: "https://discord.new/cododododoe"


async def webhook_link(app: hikari.RESTAware):
    link = links.WebhookLink.from_link(app, "https://discord.com/api/webhooks/123321123/efsdfasdsa")

    link.webhook_id  # value: 123321123
    link.token  # value: "efsdfasdsa"
    await link.fetch_webhook()  # type: hikari.IncomingWebhook
    str(link)  # value: "https://discord.com/api/webhooks/123321123/efsdfasdsa"


def make_webhook_link() -> None:
    raw_link = links.make_webhook_link(123321, "hfdssdasd")
    raw_link  # value: "https://discord.com/api/webhooks/123321/hfdssdasd"


def make_bot_invite_link() -> None:
    permissions = hikari.Permissions.BAN_MEMBERS | hikari.Permissions.MANAGE_CHANNELS
    raw_link = links.make_bot_invite(463183358445355009, permissions=permissions)
    raw_link  # value: https://discord.com/api/oauth2/authorize?client_id=463183358445355009&scope=bot&permissions=20
