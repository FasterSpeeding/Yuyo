# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Copyright (c) 2020-2023, Faster Speeding
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# pyright: reportUnknownMemberType=none
# This leads to too many false-positives around mocks.

import typing
from unittest import mock

import hikari
import pytest

import yuyo


def mock_intable(integer: int) -> mock.Mock:
    mock_str = mock.Mock(__int__=mock.Mock(return_value=integer))
    return mock_str


@pytest.mark.parametrize(
    ("invite", "expected_str"),
    [
        ("TodoketeSetsuna.saniwa", "https://discord.gg/TodoketeSetsuna.saniwa"),
        (mock.Mock(hikari.InviteCode, code="MakeAmerica_gay-again"), "https://discord.gg/MakeAmerica_gay-again"),
    ],
)
def test_make_invite_link(invite: typing.Union[str, hikari.InviteCode], expected_str: str):
    invite_link = yuyo.links.make_invite_link(invite)

    assert invite_link == expected_str


_INVITE_LINKS = [
    (" https://discord.gg/end_ofthe-world ", "end_ofthe-world"),
    (" http://discord.gg/endof ", "endof"),
    ("https://www.discord.gg/just-watching_from.afar", "just-watching_from.afar"),
    ("http://www.discord.gg/afar", "afar"),
    ("https://discord.com/invite/watching-from_afar", "watching-from_afar"),
    ("http://discord.com/invite/watching", "watching"),
    ("https://www.discordapp.com/invite/afraid_something-will-change", "afraid_something-will-change"),
    ("http://www.discordapp.com/invite/afraid", "afraid"),
    ("https://www.discord.com/invite/Im_out-Of.patience", "Im_out-Of.patience"),
    ("http://www.discord.com/invite/patience", "patience"),
    ("https://discordapp.com/invite/My-body.Is_mine", "My-body.Is_mine"),
    ("http://discordapp.com/invite/mine", "mine"),
    ("discordapp.com/invite/meowmeow", "meowmeow"),
    ("discord.com/invite/konnichiwa", "konnichiwa"),
    ("discord.gg/birdy", "birdy"),
]


class TestInviteLink:
    @pytest.mark.parametrize(("link", "invite_code"), _INVITE_LINKS)
    def test_find(self, link: str, invite_code: str):
        mock_app = mock.AsyncMock()

        invite_link = yuyo.links.InviteLink.find(
            mock_app, f"g;lll;l1;32asdsa {link} https://discord.gg/okok https://www.discordapp.com/invite/ok"
        )

        assert invite_link
        assert invite_link.code == invite_code

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_when_none(self, string: str):
        assert yuyo.links.InviteLink.find(mock.AsyncMock(), string) is None

    def test_find_iter(self):
        mock_app = mock.AsyncMock()
        string = (
            "hg4po34123 https://discord.gg/cute_egg.meow 341123dsa"
            "https://discord.new/okokoko https://www.discord.com/invite/socialist_estrogen"
        )

        links = list(yuyo.links.InviteLink.find_iter(mock_app, string))

        assert len(links) == 2
        link = links[0]
        assert link.code == "cute_egg.meow"

        link = links[1]
        assert link.code == "socialist_estrogen"

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_iter_when_none(self, string: str):
        assert list(yuyo.links.InviteLink.find_iter(mock.AsyncMock(), string)) == []

    @pytest.mark.parametrize(("link", "invite_code"), _INVITE_LINKS)
    def test_from_link(self, link: str, invite_code: str):
        mock_app = mock.AsyncMock()

        invite_link = yuyo.links.InviteLink.from_link(mock_app, link)

        assert invite_link.code == invite_code

    @pytest.mark.parametrize("string", ["lgpfrp0342", "https://discord.com/api/v43"])
    def test_from_link_when_invalid_link(self, string: str):
        with pytest.raises(ValueError, match="Link doesn't match pattern"):
            yuyo.links.InviteLink.from_link(mock.AsyncMock(), string)

    def test_code_property(self):
        link = yuyo.links.InviteLink(_app=mock.AsyncMock(), _code="Brisket")

        assert link.code == "Brisket"

    @pytest.mark.asyncio()
    async def test_fetch(self):
        mock_app = mock.AsyncMock()
        link = yuyo.links.InviteLink(_app=mock_app, _code="Brisket")

        result = await link.fetch()

        assert result is mock_app.rest.fetch_invite.return_value
        mock_app.rest.fetch_invite.assert_awaited_once_with("Brisket")

    def test_get(self):
        mock_app = mock.Mock()
        link = yuyo.links.InviteLink(_app=mock_app, _code="Brisket")

        result = link.get()

        assert result is mock_app.cache.get_invite.return_value
        mock_app.cache.get_invite.assert_called_once_with("Brisket")

    def test_get_when_cacheless(self):
        mock_app = mock.Mock(hikari.RESTAware)
        link = yuyo.links.InviteLink(_app=mock_app, _code="Brisket")

        result = link.get()

        assert result is None


@pytest.mark.parametrize(
    ("guild", "channel", "message", "expected_str"),
    [
        (123321, 432123, 56234, "https://discord.com/channels/123321/432123/56234"),
        (None, 54234, 123764, "https://discord.com/channels/@me/54234/123764"),
        (mock_intable(431), mock_intable(5413), mock_intable(12331), "https://discord.com/channels/431/5413/12331"),
        (None, mock_intable(3122), mock_intable(54312), "https://discord.com/channels/@me/3122/54312"),
    ],
)
def test_make_message_link(
    guild: typing.Optional[hikari.SnowflakeishOr[hikari.PartialGuild]],
    channel: hikari.SnowflakeishOr[hikari.PartialChannel],
    message: hikari.SnowflakeishOr[hikari.PartialMessage],
    expected_str: str,
):
    result = yuyo.links.make_message_link(channel, message, guild=guild)

    assert result == expected_str


_MESSAGE_LINKS = [
    (" https://discord.com/channels/654234/234765/8763245 ", 654234, 234765, 8763245),
    (" http://discord.com/channels/32232/45333/5434 ", 32232, 45333, 5434),
    ("https://discord.com/channels/@me/6541234/123321", None, 6541234, 123321),
    ("http://discord.com/channels/@me/22131/22312", None, 22131, 22312),
    ("https://www.discordapp.com/channels/65546323/1235423/12332123", 65546323, 1235423, 12332123),
    ("http://www.discordapp.com/channels/22233/444555/66365423", 22233, 444555, 66365423),
    ("https://www.discordapp.com/channels/@me/65234/78657", None, 65234, 78657),
    ("http://www.discordapp.com/channels/@me/43321/23121", None, 43321, 23121),
    ("https://www.discord.com/channels/654234/321654/123654", 654234, 321654, 123654),
    ("http://www.discord.com/channels/54234/5423423/32123", 54234, 5423423, 32123),
    ("https://www.discord.com/channels/@me/542123/654234", None, 542123, 654234),
    ("http://www.discord.com/channels/@me/4312312/653423", None, 4312312, 653423),
    ("https://discordapp.com/channels/234234/342654/765456", 234234, 342654, 765456),
    ("http://discordapp.com/channels/323241/43453/542312", 323241, 43453, 542312),
    ("https://discordapp.com/channels/@me/6543345/234431", None, 6543345, 234431),
    ("http://discordapp.com/channels/@me/432341/6545234", None, 432341, 6545234),
]


class TestMessageLink:
    @pytest.mark.parametrize(("link", "guild_id", "channel_id", "message_id"), _MESSAGE_LINKS)
    def test_find(self, link: str, guild_id: typing.Optional[int], channel_id: int, message_id: int):
        mock_app = mock.AsyncMock()

        message_link = yuyo.links.MessageLink.find(
            mock_app, f"g;lll;l1;32asdsa {link} https://discord.com/channels/123/321/431"
        )

        assert message_link
        assert message_link.guild_id == guild_id
        assert message_link.channel_id == channel_id
        assert message_link.message_id == message_id

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_when_none(self, string: str):
        assert yuyo.links.MessageLink.find(mock.AsyncMock(), string) is None

    def test_find_iter(self):
        mock_app = mock.AsyncMock()
        string = (
            "hg4po34123 https://discord.com/channels/341123/43213/43212 341123dsa"
            "https://discord.com/api/ https://www.discordapp.com/channels/@me/123/321"
        )

        links = list(yuyo.links.MessageLink.find_iter(mock_app, string))

        assert len(links) == 2
        link = links[0]
        assert link.guild_id == 341123
        assert link.channel_id == 43213
        assert link.message_id == 43212

        link = links[1]
        assert link.guild_id is None
        assert link.channel_id == 123
        assert link.message_id == 321

    @pytest.mark.parametrize(
        "string",
        ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123", "discord.com/channels/341123/43213/43212"],
    )
    def test_find_iter_when_none(self, string: str):
        assert list(yuyo.links.MessageLink.find_iter(mock.AsyncMock(), string)) == []

    @pytest.mark.parametrize(("link", "guild_id", "channel_id", "message_id"), _MESSAGE_LINKS)
    def test_from_link(self, link: str, guild_id: typing.Optional[int], channel_id: int, message_id: int):
        mock_app = mock.AsyncMock()

        message_link = yuyo.links.MessageLink.from_link(mock_app, link)

        assert message_link.guild_id == guild_id
        assert message_link.channel_id == channel_id
        assert message_link.message_id == message_id

    @pytest.mark.parametrize(
        "string", ["lgpfrp0342", "https://discord.com/api/v43", "discord.com/channels/341123/43213/43212"]
    )
    def test_from_link_when_invalid_link(self, string: str):
        with pytest.raises(ValueError, match="Link doesn't match pattern"):
            yuyo.links.MessageLink.from_link(mock.AsyncMock(), string)

    def test_str_cast(self):
        link = yuyo.links.MessageLink(
            _app=mock.AsyncMock(),
            _channel_id=hikari.Snowflake(543123),
            _guild_id=hikari.Snowflake(123321123),
            _message_id=hikari.Snowflake(54123123),
        )

        assert str(link) == "https://discord.com/channels/123321123/543123/54123123"

    def test_str_cast_when_in_dm(self):
        link = yuyo.links.MessageLink(
            _app=mock.AsyncMock(),
            _channel_id=hikari.Snowflake(21334123),
            _guild_id=None,
            _message_id=hikari.Snowflake(6565234),
        )

        assert str(link) == "https://discord.com/channels/@me/21334123/6565234"

    def test_channel_id_property(self):
        link = yuyo.links.MessageLink(
            _app=mock.AsyncMock(),
            _channel_id=hikari.Snowflake(65445234),
            _guild_id=hikari.Snowflake(54331452345),
            _message_id=hikari.Snowflake(123234321123),
        )

        assert link.channel_id == 65445234

    def test_guild_id_property(self):
        link = yuyo.links.MessageLink(
            _app=mock.AsyncMock(),
            _channel_id=hikari.Snowflake(231123),
            _guild_id=hikari.Snowflake(123312),
            _message_id=hikari.Snowflake(5431231),
        )

        assert link.guild_id == 123312

    def test_is_dm_link_property(self):
        link = yuyo.links.MessageLink(
            _app=mock.AsyncMock(),
            _channel_id=hikari.Snowflake(231123),
            _guild_id=hikari.Snowflake(123312),
            _message_id=hikari.Snowflake(5431231),
        )

        assert link.is_dm_link is False

    def test_is_dm_link_property_when_is_dm(self):
        link = yuyo.links.MessageLink(
            _app=mock.AsyncMock(),
            _channel_id=hikari.Snowflake(231123),
            _guild_id=None,
            _message_id=hikari.Snowflake(5431231),
        )

        assert link.is_dm_link is True

    def test_message_id_property(self):
        link = yuyo.links.MessageLink(
            _app=mock.AsyncMock(),
            _channel_id=hikari.Snowflake(765567),
            _guild_id=hikari.Snowflake(543345),
            _message_id=hikari.Snowflake(123321123),
        )

        assert link.message_id == 123321123

    @pytest.mark.asyncio()
    async def test_fetch(self):
        mock_app = mock.AsyncMock()
        webhook = yuyo.links.MessageLink(
            _app=mock_app,
            _channel_id=hikari.Snowflake(1223322),
            _guild_id=hikari.Snowflake(423123),
            _message_id=hikari.Snowflake(6521312),
        )

        result = await webhook.fetch()

        assert result is mock_app.rest.fetch_message.return_value
        mock_app.rest.fetch_message.assert_awaited_once_with(1223322, 6521312)

    def test_get(self):
        mock_app = mock.Mock()
        webhook = yuyo.links.MessageLink(
            _app=mock_app,
            _channel_id=hikari.Snowflake(123321123),
            _guild_id=hikari.Snowflake(234432234),
            _message_id=hikari.Snowflake(541123123),
        )

        result = webhook.get()

        assert result is mock_app.cache.get_message.return_value
        mock_app.cache.get_message.assert_called_once_with(541123123)

    def test_get_when_cacheless(self):
        mock_app = mock.Mock(hikari.RESTAware)
        webhook = yuyo.links.MessageLink(
            _app=mock_app,
            _channel_id=hikari.Snowflake(123321123),
            _guild_id=hikari.Snowflake(234432234),
            _message_id=hikari.Snowflake(541123123),
        )

        result = webhook.get()

        assert result is None


@pytest.mark.parametrize(
    ("template", "expected_str"),
    [
        ("trying_To-make.History", "https://discord.new/trying_To-make.History"),
        (mock.Mock(hikari.Template, code="standingHere.iRealise"), "https://discord.new/standingHere.iRealise"),
    ],
)
def test_make_template_link(template: typing.Union[str, hikari.Template], expected_str: str):
    template_link = yuyo.links.make_template_link(template)

    assert template_link == expected_str


_TEMPLATE_LINKS = [
    (" https://discord.new/i_didnt-hate.IT ", "i_didnt-hate.IT"),
    (" http://discord.new/hate ", "hate"),
    ("https://www.discord.new/UnlessIjust_had-to_do.something-bout-it", "UnlessIjust_had-to_do.something-bout-it"),
    ("http://www.discord.new/to_do", "to_do"),
    ("https://discord.com/template/I-Didnt_not-even_like-it", "I-Didnt_not-even_like-it"),
    ("http://discord.com/template/like", "like"),
    ("https://www.discordapp.com/template/I-know_who.you-are", "I-know_who.you-are"),
    ("http://www.discordapp.com/template/know-who", "know-who"),
    ("https://www.discord.com/template/Im-not_leaving.youagain", "Im-not_leaving.youagain"),
    ("http://www.discord.com/template/youagain", "youagain"),
    ("https://discordapp.com/template/Thereis_no-where-to.go-back", "Thereis_no-where-to.go-back"),
    ("http://discordapp.com/template/to-go", "to-go"),
]


class TestTemplateLink:
    @pytest.mark.parametrize(("link", "template_code"), _TEMPLATE_LINKS)
    def test_find(self, link: str, template_code: str):
        mock_app = mock.AsyncMock()

        template_link = yuyo.links.TemplateLink.find(
            mock_app, f"g;lll;l1;32asdsa {link} https://discord.new/flint https://www.discordapp.com/template/aaa"
        )

        assert template_link
        assert template_link.code == template_code

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_when_none(self, string: str):
        assert yuyo.links.TemplateLink.find(mock.AsyncMock(), string) is None

    def test_find_iter(self):
        mock_app = mock.AsyncMock()
        string = (
            "hg4po34123 https://discord.new/motivated_egg.nyaa 341123dsa"
            "https://discord.gg/okokoko https://www.discord.com/template/free-estrogen_for.all"
        )

        links = list(yuyo.links.TemplateLink.find_iter(mock_app, string))

        assert len(links) == 2
        link = links[0]
        assert link.code == "motivated_egg.nyaa"

        link = links[1]
        assert link.code == "free-estrogen_for.all"

    @pytest.mark.parametrize(
        "string",
        [
            "lkdfoklfdspo32409324",
            "https://discord.com/api/v9/users/o123123",
            "discord.new/Turn-the_grey.haze-into_sky-blue",
        ],
    )
    def test_find_iter_when_none(self, string: str):
        assert list(yuyo.links.TemplateLink.find_iter(mock.AsyncMock(), string)) == []

    @pytest.mark.parametrize(("link", "template_code"), _TEMPLATE_LINKS)
    def test_from_link(self, link: str, template_code: str):
        mock_app = mock.AsyncMock()

        template_link = yuyo.links.TemplateLink.from_link(mock_app, link)

        assert template_link.code == template_code

    @pytest.mark.parametrize(
        "string", ["lgpfrp0342", "https://discord.com/api/v43", "discord.new/Turn-the_grey.haze-into_sky-blue"]
    )
    def test_from_link_when_invalid_link(self, string: str):
        with pytest.raises(ValueError, match="Link doesn't match pattern"):
            yuyo.links.TemplateLink.from_link(mock.AsyncMock(), string)

    def test_str_cast(self):
        link = yuyo.links.TemplateLink(_app=mock.AsyncMock(), _code="Turn-the_grey.haze-into_sky-blue")

        assert str(link) == "https://discord.new/Turn-the_grey.haze-into_sky-blue"

    def test_code_property(self):
        link = yuyo.links.TemplateLink(_app=mock.AsyncMock(), _code="I_could-go.home")

        assert link.code == "I_could-go.home"

    @pytest.mark.asyncio()
    async def test_fetch(self):
        mock_app = mock.AsyncMock()
        link = yuyo.links.TemplateLink(_app=mock_app, _code="Brisket")

        result = await link.fetch()

        assert result is mock_app.rest.fetch_template.return_value
        mock_app.rest.fetch_template.assert_awaited_once_with("Brisket")


@pytest.mark.parametrize(
    ("webhook", "token", "expected_str"),
    [
        (1235412, "fogof._21231123", "https://discord.com/api/webhooks/1235412/fogof._21231123"),
        (mock_intable(4312123), "gflop2l3434", "https://discord.com/api/webhooks/4312123/gflop2l3434"),
    ],
)
def test_make_webhook_link(webhook: hikari.SnowflakeishOr[hikari.PartialWebhook], token: str, expected_str: str):
    result = yuyo.links.make_webhook_link(webhook, token)

    assert result == expected_str


_WEBHOOK_LINKS = [
    (" https://discord.com/api/webhooks/123432/My_withoutme-imthe1.2blame ", 123432, "My_withoutme-imthe1.2blame"),
    (" http://discord.com/api/webhooks/4322/blame ", 4322, "blame"),
    ("https://www.discordapp.com/api/v69/webhooks/5623123/boom-boom", 5623123, "boom-boom"),
    ("http://www.discordapp.com/api/v69/webhooks/342234/boom", 342234, "boom"),
    ("https://discordapp.com/api/v96/webhooks/1231/everyones_voice.nowhere-2-go", 1231, "everyones_voice.nowhere-2-go"),
    ("http://discordapp.com/api/v96/webhooks/3432123/everyones_voice", 3432123, "everyones_voice"),
    ("https://www.discord.com/api/v123/webhooks/56345/i-can-feel_the.light", 56345, "i-can-feel_the.light"),
    ("http://www.discord.com/api/v123/webhooks/453345/light", 453345, "light"),
    ("https://www.discordapp.com/api/webhooks/123321/im-not-waiting.", 123321, "im-not-waiting."),
    ("http://www.discordapp.com/api/webhooks/12332432/waiting", 12332432, "waiting"),
    ("https://www.discord.com/api/webhooks/123/for.a-santa_claus", 123, "for.a-santa_claus"),
    ("http://www.discord.com/api/webhooks/6544/santa_claus", 6544, "santa_claus"),
    ("https://discordapp.com/api/webhooks/45555/ik-all_about.it", 45555, "ik-all_about.it"),
    ("http://discordapp.com/api/webhooks/435234/all_about.it", 435234, "all_about.it"),
    ("https://discord.com/api/v420/webhooks/65434/lie_lie-lie.", 65434, "lie_lie-lie."),
    ("http://discord.com/api/v420/webhooks/654234/lie_lie", 654234, "lie_lie"),
]


class TestWebhookLink:
    @pytest.mark.parametrize(("link", "webhook_id", "token"), _WEBHOOK_LINKS)
    def test_find(self, link: str, webhook_id: int, token: str):
        mock_app = mock.AsyncMock()

        webhook = yuyo.links.WebhookLink.find(
            mock_app, f"fg123 123 https://discord {link} https://discord.com/api/webhooks/123/321"
        )

        assert webhook
        assert webhook.app is mock_app
        assert webhook.webhook_id == webhook_id
        assert webhook.token == token

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_when_none(self, string: str):
        assert yuyo.links.WebhookLink.find(mock.AsyncMock(), string) is None

    def test_find_iter(self):
        mock_app = mock.AsyncMock()
        string = (
            "hg4po34123 https://discord.com/api/webhooks/5431231/i-am_the.catgirl 341123dsa"
            "https://discord.com/api/ https://www.discordapp.com/api/v94/webhooks/3123123/welcome-my.friend"
        )

        links = list(yuyo.links.WebhookLink.find_iter(mock_app, string))

        assert len(links) == 2
        link = links[0]
        assert link.app is mock_app
        assert link.webhook_id == 5431231
        assert link.token == "i-am_the.catgirl"  # noqa: S105

        link = links[1]
        assert link.app is mock_app
        assert link.webhook_id == 3123123
        assert link.token == "welcome-my.friend"  # noqa: S105

    @pytest.mark.parametrize(
        "string",
        [
            "lkdfoklfdspo32409324",
            "https://discord.com/api/v9/users/o123123",
            "discord.com/api/v420/webhooks/65434/lie_lie-lie",
        ],
    )
    def test_find_iter_when_none(self, string: str):
        assert list(yuyo.links.WebhookLink.find_iter(mock.AsyncMock(), string)) == []

    @pytest.mark.parametrize(("link", "webhook_id", "token"), _WEBHOOK_LINKS)
    def test_from_link(self, link: str, webhook_id: int, token: str):
        mock_app = mock.AsyncMock()

        webhook = yuyo.links.WebhookLink.from_link(mock_app, link)

        assert webhook.app is mock_app
        assert webhook.webhook_id == webhook_id
        assert webhook.token == token

    @pytest.mark.parametrize(
        "string", ["lgpfrp0342", "https://discord.com/api/v43", "discord.com/api/v420/webhooks/65434/lie_lie-lie"]
    )
    def test_from_link_when_invalid_link(self, string: str):
        with pytest.raises(ValueError, match="Link doesn't match pattern"):
            yuyo.links.WebhookLink.from_link(mock.AsyncMock(), string)

    def test_str_cast(self):
        webhook = yuyo.links.WebhookLink(  # noqa: S106
            _app=mock.AsyncMock(), _token="lielielie", _webhook_id=hikari.Snowflake(123342)
        )

        assert str(webhook) == "https://discord.com/api/webhooks/123342/lielielie"

    def test_app_property(self):
        mock_app = mock.AsyncMock()
        webhook = yuyo.links.WebhookLink(  # noqa: S106
            _app=mock_app, _token="the town inside me", _webhook_id=hikari.Snowflake(4321123)
        )

        assert webhook.app is mock_app

    def test_webhook_id_property(self):
        webhook = yuyo.links.WebhookLink(  # noqa: S106
            _app=mock.AsyncMock(), _token="and everyone's voice", _webhook_id=hikari.Snowflake(67345)
        )

        assert webhook.webhook_id == 67345

    def test_token(self):
        webhook = yuyo.links.WebhookLink(  # noqa: S106
            _app=mock.AsyncMock(), _token="Me without me", _webhook_id=hikari.Snowflake(452213)
        )

        assert webhook.token == "Me without me"  # noqa: S105

    @pytest.mark.asyncio()
    async def test_fetch(self):
        mock_app = mock.AsyncMock()
        mock_app.rest.fetch_webhook.return_value = mock.Mock(hikari.IncomingWebhook)
        webhook = yuyo.links.WebhookLink(  # noqa: S106
            _app=mock_app, _token="I'm the one to blame", _webhook_id=hikari.Snowflake(654345)
        )

        result = await webhook.fetch()

        assert result is mock_app.rest.fetch_webhook.return_value
        mock_app.rest.fetch_webhook.assert_awaited_once_with(654345, token="I'm the one to blame")  # noqa: S106
