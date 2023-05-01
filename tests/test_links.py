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
    ("https://ptb.discord.com/invite/invite-it.uwu", "invite-it.uwu"),
    ("http://ptb.discord.com/invite/words", "words"),
    ("https://ptb.discordapp.com/invite/invites-it.uwu", "invites-it.uwu"),
    ("http://ptb.discordapp.com/invite/word", "word"),
    ("https://canary.discord.com/invite/beep-beep.beep", "beep-beep.beep"),
    ("http://canary.discord.com/invite/boop", "boop"),
    ("https://canary.discordapp.com/invite/earth-bound.beep", "earth-bound.beep"),
    ("http://canary.discordapp.com/invite/mother", "mother"),
    ("discordapp.com/invite/meowmeow", "meowmeow"),
    ("discord.com/invite/konnichiwa", "konnichiwa"),
    ("discord.gg/birdy", "birdy"),
    ("ptb.discordapp.com/invite/aaa", "aaa"),
    ("ptb.discord.com/invite/aaaaa", "aaaaa"),
    ("canary.discordapp.com/invite/interesting", "interesting"),
    ("canary.discord.com/invite/interest", "interest"),
]


class TestInviteLink:
    @pytest.mark.parametrize(("raw_link", "invite_code"), _INVITE_LINKS)
    def test_find(self, raw_link: str, invite_code: str):
        mock_app = mock.AsyncMock()

        link = yuyo.links.InviteLink.find(
            mock_app, f"g;lll;l1;32asdsa {raw_link} https://discord.gg/okok https://www.discordapp.com/invite/ok"
        )

        assert link
        assert link.code == invite_code

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_when_none(self, string: str):
        assert yuyo.links.InviteLink.find(mock.AsyncMock(), string) is None

    def test_find_iter(self):
        mock_app = mock.AsyncMock()
        string = (
            "hg4po34123 https://discord.gg/cute_egg.meow 341123dsa"
            "https://discord.new/okokoko https://www.discord.com/invite/socialist_estrogen"
        )

        assert list(yuyo.links.InviteLink.find_iter(mock_app, string)) == [
            yuyo.links.InviteLink(_app=mock_app, _code="cute_egg.meow"),
            yuyo.links.InviteLink(_app=mock_app, _code="socialist_estrogen"),
        ]

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_iter_when_none(self, string: str):
        assert list(yuyo.links.InviteLink.find_iter(mock.AsyncMock(), string)) == []

    @pytest.mark.parametrize(("raw_link", "invite_code"), _INVITE_LINKS)
    def test_from_link(self, raw_link: str, invite_code: str):
        mock_app = mock.AsyncMock()

        link = yuyo.links.InviteLink.from_link(mock_app, raw_link)

        assert link.code == invite_code

    @pytest.mark.parametrize("string", ["lgpfrp0342", "https://discord.com/api/v43"])
    def test_from_link_when_invalid_link(self, string: str):
        with pytest.raises(ValueError, match="Link doesn't match pattern"):
            yuyo.links.InviteLink.from_link(mock.AsyncMock(), string)

    @pytest.mark.asyncio()
    async def test_fetch_invite(self):
        mock_app = mock.AsyncMock()
        link = yuyo.links.InviteLink(_app=mock_app, _code="Brisket")

        result = await link.fetch_invite()

        assert result is mock_app.rest.fetch_invite.return_value
        mock_app.rest.fetch_invite.assert_awaited_once_with("Brisket")

    def test_get_invite(self):
        mock_app = mock.Mock()
        link = yuyo.links.InviteLink(_app=mock_app, _code="Brisket")

        result = link.get_invite()

        assert result is mock_app.cache.get_invite.return_value
        mock_app.cache.get_invite.assert_called_once_with("Brisket")

    def test_get_invite_when_cacheless(self):
        mock_app = mock.Mock(hikari.RESTAware)
        link = yuyo.links.InviteLink(_app=mock_app, _code="Brisket")

        result = link.get_invite()

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


_MESSAGE_LINKS: list[tuple[str, typing.Optional[int], int, int]] = [
    (" https://discord.com/channels/654234/234765/8763245 ", 654234, 234765, 8763245),
    (" http://discord.com/channels/32232/45333/5434 ", 32232, 45333, 5434),
    ("https://discord.com/channels/@me/6541234/123321", None, 6541234, 123321),
    ("http://discord.com/channels/@me/22131/22312", None, 22131, 22312),
    ("https://discord.com/channels/54234123/321233/4443333", 54234123, 321233, 4443333),
    ("http://discord.com/channels/54234234/5431233/6541232", 54234234, 5431233, 6541232),
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
    ("https://ptb.discord.com/channels/@me/1233222/5123321", None, 1233222, 5123321),
    ("http://ptb.discord.com/channels/@me/32123321/5423432", None, 32123321, 5423432),
    ("https://ptb.discord.com/channels/4331233/4323132/43123431", 4331233, 4323132, 43123431),
    ("http://ptb.discord.com/channels/544332123/43523123/4323432", 544332123, 43523123, 4323432),
    ("https://ptb.discordapp.com/channels/@me/6753452/45312343", None, 6753452, 45312343),
    ("http://ptb.discordapp.com/channels/@me/65445345/654234", None, 65445345, 654234),
    ("https://ptb.discordapp.com/channels/342123321/2345432343/6572343", 342123321, 2345432343, 6572343),
    ("http://ptb.discordapp.com/channels/53324432/43212343223/65445234", 53324432, 43212343223, 65445234),
    ("https://canary.discord.com/channels/@me/321452/54323", None, 321452, 54323),
    ("http://canary.discord.com/channels/@me/6542344/654234", None, 6542344, 654234),
    ("https://canary.discord.com/channels/654456234/54345543234/6542344", 654456234, 54345543234, 6542344),
    ("http://canary.discord.com/channels/876432344/453123321/32421332", 876432344, 453123321, 32421332),
    ("https://canary.discordapp.com/channels/@me/21332143/543234123", None, 21332143, 543234123),
    ("http://canary.discordapp.com/channels/@me/56423412/654234431", None, 56423412, 654234431),
    ("https://canary.discordapp.com/channels/654765324/654234432/54345234", 654765324, 654234432, 54345234),
    ("http://canary.discordapp.com/channels/7656432344/4536454/765345234", 7656432344, 4536454, 765345234),
]


class TestMessageLink:
    @pytest.mark.parametrize(("raw_link", "guild_id", "channel_id", "message_id"), _MESSAGE_LINKS)
    def test_find(self, raw_link: str, guild_id: typing.Optional[int], channel_id: int, message_id: int):
        mock_app = mock.AsyncMock()

        link = yuyo.links.MessageLink.find(
            mock_app, f"g;lll;l1;32asdsa {raw_link} https://discord.com/channels/123/321/431"
        )

        assert link
        assert link.guild_id == guild_id
        assert link.channel_id == channel_id
        assert link.message_id == message_id

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_when_none(self, string: str):
        assert yuyo.links.MessageLink.find(mock.AsyncMock(), string) is None

    def test_find_iter(self):
        mock_app = mock.AsyncMock()
        string = (
            "hg4po34123 https://discord.com/channels/341123/43213/43212 341123dsa"
            "https://discord.com/api/ https://www.discordapp.com/channels/@me/123/321"
        )

        assert list(yuyo.links.MessageLink.find_iter(mock_app, string)) == [
            yuyo.links.MessageLink(
                _app=mock_app,
                _guild_id=hikari.Snowflake(341123),
                _channel_id=hikari.Snowflake(43213),
                _message_id=hikari.Snowflake(43212),
            ),
            yuyo.links.MessageLink(
                _app=mock_app, _guild_id=None, _channel_id=hikari.Snowflake(123), _message_id=hikari.Snowflake(321)
            ),
        ]

    @pytest.mark.parametrize(
        "string",
        ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123", "discord.com/channels/341123/43213/43212"],
    )
    def test_find_iter_when_none(self, string: str):
        assert list(yuyo.links.MessageLink.find_iter(mock.AsyncMock(), string)) == []

    @pytest.mark.parametrize(("raw_link", "guild_id", "channel_id", "message_id"), _MESSAGE_LINKS)
    def test_from_link(self, raw_link: str, guild_id: typing.Optional[int], channel_id: int, message_id: int):
        mock_app = mock.AsyncMock()

        link = yuyo.links.MessageLink.from_link(mock_app, raw_link)

        assert link.guild_id == guild_id
        assert link.channel_id == channel_id
        assert link.message_id == message_id

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

    @pytest.mark.asyncio()
    async def test_fetch_message(self):
        mock_app = mock.AsyncMock()
        link = yuyo.links.MessageLink(
            _app=mock_app,
            _channel_id=hikari.Snowflake(1223322),
            _guild_id=hikari.Snowflake(423123),
            _message_id=hikari.Snowflake(6521312),
        )

        result = await link.fetch_message()

        assert result is mock_app.rest.fetch_message.return_value
        mock_app.rest.fetch_message.assert_awaited_once_with(1223322, 6521312)

    def test_get_message(self):
        mock_app = mock.Mock()
        link = yuyo.links.MessageLink(
            _app=mock_app,
            _channel_id=hikari.Snowflake(123321123),
            _guild_id=hikari.Snowflake(234432234),
            _message_id=hikari.Snowflake(541123123),
        )

        result = link.get_message()

        assert result is mock_app.cache.get_message.return_value
        mock_app.cache.get_message.assert_called_once_with(541123123)

    def test_get_message_when_cacheless(self):
        mock_app = mock.Mock(hikari.RESTAware)
        link = yuyo.links.MessageLink(
            _app=mock_app,
            _channel_id=hikari.Snowflake(123321123),
            _guild_id=hikari.Snowflake(234432234),
            _message_id=hikari.Snowflake(541123123),
        )

        result = link.get_message()

        assert result is None


@pytest.mark.parametrize(
    ("guild", "channel", "expected_str"),
    [
        (53452, 34123, "https://discord.com/channels/53452/34123"),
        (None, 77666, "https://discord.com/channels/@me/77666"),
        (mock_intable(666), mock_intable(543), "https://discord.com/channels/666/543"),
        (None, mock_intable(432123), "https://discord.com/channels/@me/432123"),
    ],
)
def test_make_channel_link(
    guild: typing.Optional[hikari.SnowflakeishOr[hikari.PartialGuild]],
    channel: hikari.SnowflakeishOr[hikari.PartialChannel],
    expected_str: str,
):
    result = yuyo.links.make_channel_link(channel, guild=guild)

    assert result == expected_str


_CHANNEL_LINKS: list[tuple[str, typing.Optional[int], int]] = [
    *[entry[:-1] for entry in _MESSAGE_LINKS],
    (" https://discord.com/channels/543345/123123 ", 543345, 123123),
    (" http://discord.com/channels/123321/543345 ", 123321, 543345),
    ("https://discord.com/channels/@me/45312343", None, 45312343),
    ("http://discord.com/channels/@me/423443", None, 423443),
    ("https://discord.com/channels/12312353/2523423", 12312353, 2523423),
    ("http://discord.com/channels/745645234/45334534", 745645234, 45334534),
    ("https://www.discordapp.com/channels/56445623/5234234", 56445623, 5234234),
    ("http://www.discordapp.com/channels/23443233/5644563", 23443233, 5644563),
    ("https://www.discordapp.com/channels/@me/5644566", None, 5644566),
    ("http://www.discordapp.com/channels/@me/45345", None, 45345),
    ("https://www.discord.com/channels/756456/23423423", 756456, 23423423),
    ("http://www.discord.com/channels/4322344/675345", 4322344, 675345),
    ("https://www.discord.com/channels/@me/654456345", None, 654456345),
    ("http://www.discord.com/channels/@me/34554334", None, 34554334),
    ("https://discordapp.com/channels/67545345/234432234", 67545345, 234432234),
    ("http://discordapp.com/channels/645456345/65445645", 645456345, 65445645),
    ("https://discordapp.com/channels/@me/234432453", None, 234432453),
    ("http://discordapp.com/channels/@me/6543423", None, 6543423),
    ("https://ptb.discord.com/channels/@me/6534554", None, 6534554),
    ("http://ptb.discord.com/channels/@me/654345", None, 654345),
    ("https://ptb.discord.com/channels/6544564/8766745", 6544564, 8766745),
    ("http://ptb.discord.com/channels/5642344/6544566", 5642344, 6544566),
    ("https://ptb.discordapp.com/channels/@me/453345654", None, 453345654),
    ("http://ptb.discordapp.com/channels/@me/345234432", None, 345234432),
    ("https://ptb.discordapp.com/channels/6544564/34523443", 6544564, 34523443),
    ("http://ptb.discordapp.com/channels/654345234/543234123", 654345234, 543234123),
    ("https://canary.discord.com/channels/@me/7653455", None, 7653455),
    ("http://canary.discord.com/channels/@me/234412", None, 234412),
    ("https://canary.discord.com/channels/345234432/6542345", 345234432, 6542345),
    ("http://canary.discord.com/channels/56345234/56423443", 56345234, 56423443),
    ("https://canary.discordapp.com/channels/@me/65434545", None, 65434545),
    ("http://canary.discordapp.com/channels/@me/7654563", None, 7654563),
    ("https://canary.discordapp.com/channels/7653455/456765", 7653455, 456765),
    ("http://canary.discordapp.com/channels/65445234/654456345", 65445234, 654456345),
]


class TestChannelInvite:
    @pytest.mark.parametrize(("raw_link", "guild_id", "channel_id"), _CHANNEL_LINKS)
    def test_find(self, raw_link: str, guild_id: typing.Optional[int], channel_id: int):
        mock_app = mock.AsyncMock()

        link = yuyo.links.ChannelLink.find(
            mock_app, f"g;lll;l1;32asdsa {raw_link} https://discord.com/channels/54321/12332"
        )

        assert link
        assert link.guild_id == guild_id
        assert link.channel_id == channel_id

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_when_none(self, string: str):
        assert yuyo.links.ChannelLink.find(mock.AsyncMock(), string) is None

    def test_find_iter(self):
        mock_app = mock.AsyncMock()
        string = (
            "hg4po34123 https://discord.com/channels/3212/4312312 341123dsa"
            "https://discord.com/api/ https://www.discordapp.com/channels/@me/31123"
        )

        assert list(yuyo.links.ChannelLink.find_iter(mock_app, string)) == [
            yuyo.links.ChannelLink(
                _app=mock_app, _guild_id=hikari.Snowflake(3212), _channel_id=hikari.Snowflake(4312312)
            ),
            yuyo.links.ChannelLink(_app=mock_app, _guild_id=None, _channel_id=hikari.Snowflake(31123)),
        ]

    @pytest.mark.parametrize(
        "string",
        ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123", "discord.com/channels/341123/43213/43212"],
    )
    def test_find_iter_when_none(self, string: str):
        assert list(yuyo.links.ChannelLink.find_iter(mock.AsyncMock(), string)) == []

    @pytest.mark.parametrize(("raw_link", "guild_id", "channel_id"), _CHANNEL_LINKS)
    def test_from_link(self, raw_link: str, guild_id: typing.Optional[int], channel_id: int):
        mock_app = mock.AsyncMock()

        link = yuyo.links.ChannelLink.from_link(mock_app, raw_link)

        assert link.guild_id == guild_id
        assert link.channel_id == channel_id

    @pytest.mark.parametrize(
        "string", ["lgpfrp0342", "https://discord.com/api/v43", "discord.com/channels/341123/43213"]
    )
    def test_from_link_when_invalid_link(self, string: str):
        with pytest.raises(ValueError, match="Link doesn't match pattern"):
            yuyo.links.ChannelLink.from_link(mock.AsyncMock(), string)

    def test_is_dm_link_property(self):
        link = yuyo.links.ChannelLink(
            _app=mock.AsyncMock(), _channel_id=hikari.Snowflake(123321), _guild_id=hikari.Snowflake(4434)
        )

        assert link.is_dm_link is False

    def test_is_dm_link_property_when_is_dm(self):
        link = yuyo.links.ChannelLink(_app=mock.AsyncMock(), _channel_id=hikari.Snowflake(543345), _guild_id=None)

        assert link.is_dm_link is True

    def test_str_cast(self):
        link = yuyo.links.ChannelLink(
            _app=mock.AsyncMock(), _channel_id=hikari.Snowflake(553212), _guild_id=hikari.Snowflake(32123)
        )

        assert str(link) == "https://discord.com/channels/32123/553212"

    def test_str_cast_when_in_dm(self):
        link = yuyo.links.ChannelLink(_app=mock.AsyncMock(), _channel_id=hikari.Snowflake(21334123), _guild_id=None)

        assert str(link) == "https://discord.com/channels/@me/21334123"

    @pytest.mark.asyncio()
    async def test_fetch_channel(self):
        mock_app = mock.AsyncMock()
        link = yuyo.links.ChannelLink(
            _app=mock_app, _guild_id=hikari.Snowflake(431123), _channel_id=hikari.Snowflake(223311)
        )

        result = await link.fetch_channel()

        assert result is mock_app.rest.fetch_channel.return_value
        mock_app.rest.fetch_channel.assert_awaited_once_with(223311)

    def test_get_channel_when_user_cache_hit(self):
        mock_app = mock.Mock()
        mock_app.cache.get_thread.return_value = None
        link = yuyo.links.ChannelLink(
            _app=mock_app, _guild_id=hikari.Snowflake(431123), _channel_id=hikari.Snowflake(65434)
        )

        result = link.get_channel()

        assert result is mock_app.cache.get_guild_channel.return_value
        mock_app.cache.get_guild_channel.assert_called_once_with(65434)

    def test_get_channel_when_thread_cache_hit(self):
        mock_app = mock.Mock()
        mock_app.cache.get_guild_channel.return_value = None
        link = yuyo.links.ChannelLink(
            _app=mock_app, _guild_id=hikari.Snowflake(431123), _channel_id=hikari.Snowflake(745234)
        )

        result = link.get_channel()

        assert result is mock_app.cache.get_thread.return_value
        mock_app.cache.get_thread.assert_called_once_with(745234)

    def test_get_channel_when_not_found(self):
        mock_app = mock.Mock()
        mock_app.cache.get_guild_channel.return_value = None
        mock_app.cache.get_thread.return_value = None
        link = yuyo.links.ChannelLink(_app=mock_app, _guild_id=None, _channel_id=hikari.Snowflake(5432134))

        result = link.get_channel()

        assert result is None
        mock_app.cache.get_guild_channel.assert_called_once_with(5432134)
        mock_app.cache.get_thread.assert_called_once_with(5432134)

    def test_get_channel_when_cacheless(self):
        mock_app = mock.Mock(hikari.RESTAware)
        link = yuyo.links.ChannelLink(
            _app=mock_app, _guild_id=hikari.Snowflake(431123), _channel_id=hikari.Snowflake(64234132)
        )

        result = link.get_channel()

        assert result is None

    @pytest.mark.asyncio()
    async def test_fetch_guild(self):
        mock_app = mock.AsyncMock()
        link = yuyo.links.ChannelLink(
            _app=mock_app, _guild_id=hikari.Snowflake(5412123), _channel_id=hikari.Snowflake(64234132)
        )

        result = await link.fetch_guild()

        assert result is mock_app.rest.fetch_guild.return_value
        mock_app.rest.fetch_guild.assert_awaited_once_with(5412123)

    @pytest.mark.asyncio()
    async def test_fetch_guild_for_dm_link(self):
        mock_app = mock.Mock()
        link = yuyo.links.ChannelLink(_app=mock_app, _guild_id=None, _channel_id=hikari.Snowflake(64234132))

        result = await link.fetch_guild()

        assert result is None

    def test_get_guild(self):
        mock_app = mock.Mock()
        link = yuyo.links.ChannelLink(
            _app=mock_app, _guild_id=hikari.Snowflake(641231), _channel_id=hikari.Snowflake(64234132)
        )

        result = link.get_guild()

        assert result is mock_app.cache.get_guild.return_value
        mock_app.cache.get_guild.assert_called_once_with(641231)

    def test_get_guild_for_dm_link(self):
        mock_app = mock.Mock()
        link = yuyo.links.ChannelLink(_app=mock_app, _guild_id=None, _channel_id=hikari.Snowflake(64234132))

        result = link.get_guild()

        assert result is None

    def test_get_guild_when_cacheless(self):
        mock_app = mock.Mock(hikari.RESTAware)
        link = yuyo.links.ChannelLink(
            _app=mock_app, _guild_id=hikari.Snowflake(431123), _channel_id=hikari.Snowflake(64234132)
        )

        result = link.get_guild()

        assert result is None


@pytest.mark.parametrize(
    ("template", "expected_str"),
    [
        ("trying_To-make.History", "https://discord.new/trying_To-make.History"),
        (mock.Mock(hikari.Template, code="standingHere.iRealise"), "https://discord.new/standingHere.iRealise"),
    ],
)
def test_make_template_link(template: typing.Union[str, hikari.Template], expected_str: str):
    result = yuyo.links.make_template_link(template)

    assert result == expected_str


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
    ("https://ptb.discord.com/template/meow_meow-m.eow", "meow_meow-m.eow"),
    ("http://ptb.discord.com/template/aaa-bbb", "aaa-bbb"),
    ("https://ptb.discordapp.com/template/bbbb_b.bbb", "bbbb_b.bbb"),
    ("http://ptb.discordapp.com/template/go-go", "go-go"),
    ("https://canary.discord.com/template/audit-me.meow", "audit-me.meow"),
    ("http://canary.discord.com/template/cheap-cheap", "cheap-cheap"),
    ("https://canary.discordapp.com/template/c-c_cc.c", "c-c_cc.c"),
    ("http://canary.discordapp.com/template/meow-meow", "meow-meow"),
]


class TestTemplateLink:
    @pytest.mark.parametrize(("raw_link", "template_code"), _TEMPLATE_LINKS)
    def test_find(self, raw_link: str, template_code: str):
        mock_app = mock.AsyncMock()

        link = yuyo.links.TemplateLink.find(
            mock_app, f"g;lll;l1;32asdsa {raw_link} https://discord.new/flint https://www.discordapp.com/template/aaa"
        )

        assert link
        assert link.code == template_code

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_when_none(self, string: str):
        assert yuyo.links.TemplateLink.find(mock.AsyncMock(), string) is None

    def test_find_iter(self):
        mock_app = mock.AsyncMock()
        string = (
            "hg4po34123 https://discord.new/motivated_egg.nyaa 341123dsa"
            "https://discord.gg/okokoko https://www.discord.com/template/free-estrogen_for.all"
        )

        assert list(yuyo.links.TemplateLink.find_iter(mock_app, string)) == [
            yuyo.links.TemplateLink(_app=mock_app, _code="motivated_egg.nyaa"),
            yuyo.links.TemplateLink(_app=mock_app, _code="free-estrogen_for.all"),
        ]

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

    @pytest.mark.parametrize(("raw_link", "template_code"), _TEMPLATE_LINKS)
    def test_from_link(self, raw_link: str, template_code: str):
        mock_app = mock.AsyncMock()

        link = yuyo.links.TemplateLink.from_link(mock_app, raw_link)

        assert link.code == template_code

    @pytest.mark.parametrize(
        "string", ["lgpfrp0342", "https://discord.com/api/v43", "discord.new/Turn-the_grey.haze-into_sky-blue"]
    )
    def test_from_link_when_invalid_link(self, string: str):
        with pytest.raises(ValueError, match="Link doesn't match pattern"):
            yuyo.links.TemplateLink.from_link(mock.AsyncMock(), string)

    def test_str_cast(self):
        link = yuyo.links.TemplateLink(_app=mock.AsyncMock(), _code="Turn-the_grey.haze-into_sky-blue")

        assert str(link) == "https://discord.new/Turn-the_grey.haze-into_sky-blue"

    @pytest.mark.asyncio()
    async def test_fetch_template(self):
        mock_app = mock.AsyncMock()
        link = yuyo.links.TemplateLink(_app=mock_app, _code="Brisket")

        result = await link.fetch_template()

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
    ("https://ptb.discord.com/api/v69/webhooks/654234/54gdfgfd.21sdfpdsaa_s-d", 654234, "54gdfgfd.21sdfpdsaa_s-d"),
    ("http://ptb.discord.com/api/v69/webhooks/45543123/fdsgfdsfad.adsfdasa_d-ss", 45543123, "fdsgfdsfad.adsfdasa_d-ss"),
    ("https://ptb.discordapp.com/api/v69/webhooks/65412376/fds-gf.ddfd_pds", 65412376, "fds-gf.ddfd_pds"),
    ("http://ptb.discordapp.com/api/v69/webhooks/1233211/gfdsad.asd-dsaasd_ss", 1233211, "gfdsad.asd-dsaasd_ss"),
    ("https://canary.discord.com/api/v69/webhooks/543345/fds.-rwewer_dsa", 543345, "fds.-rwewer_dsa"),
    ("http://canary.discord.com/api/v69/webhooks/87667/sdf-asd._ds", 87667, "sdf-asd._ds"),
    ("https://canary.discordapp.com/api/v69/webhooks/123321/asddsa.-hgfhg_a", 123321, "asddsa.-hgfhg_a"),
    ("http://canary.discordapp.com/api/v69/webhooks/7656/_fds.-erw123", 7656, "_fds.-erw123"),
]


class TestWebhookLink:
    @pytest.mark.parametrize(("raw_link", "webhook_id", "token"), _WEBHOOK_LINKS)
    def test_find(self, raw_link: str, webhook_id: int, token: str):
        mock_app = mock.AsyncMock()

        link = yuyo.links.WebhookLink.find(
            mock_app, f"fg123 123 https://discord {raw_link} https://discord.com/api/webhooks/123/321"
        )

        assert link
        assert link.app is mock_app
        assert link.webhook_id == webhook_id
        assert link.token == token

    @pytest.mark.parametrize("string", ["lkdfoklfdspo32409324", "https://discord.com/api/v9/users/o123123"])
    def test_find_when_none(self, string: str):
        assert yuyo.links.WebhookLink.find(mock.AsyncMock(), string) is None

    def test_find_iter(self):
        mock_app = mock.AsyncMock()
        string = (
            "hg4po34123 https://discord.com/api/webhooks/5431231/i-am_the.catgirl 341123dsa"
            "https://discord.com/api/ https://www.discordapp.com/api/v94/webhooks/3123123/welcome-my.friend"
        )

        assert list(yuyo.links.WebhookLink.find_iter(mock_app, string)) == [
            yuyo.links.WebhookLink(  # noqa: S106
                _app=mock_app, _webhook_id=hikari.Snowflake(5431231), _token="i-am_the.catgirl"
            ),
            yuyo.links.WebhookLink(  # noqa: S106
                _app=mock_app, _webhook_id=hikari.Snowflake(3123123), _token="welcome-my.friend"
            ),
        ]

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

    @pytest.mark.parametrize(("raw_link", "webhook_id", "token"), _WEBHOOK_LINKS)
    def test_from_link(self, raw_link: str, webhook_id: int, token: str):
        mock_app = mock.AsyncMock()

        link = yuyo.links.WebhookLink.from_link(mock_app, raw_link)

        assert link.app is mock_app
        assert link.webhook_id == webhook_id
        assert link.token == token

    @pytest.mark.parametrize(
        "string", ["lgpfrp0342", "https://discord.com/api/v43", "discord.com/api/v420/webhooks/65434/lie_lie-lie"]
    )
    def test_from_link_when_invalid_link(self, string: str):
        with pytest.raises(ValueError, match="Link doesn't match pattern"):
            yuyo.links.WebhookLink.from_link(mock.AsyncMock(), string)

    def test_str_cast(self):
        link = yuyo.links.WebhookLink(  # noqa: S106
            _app=mock.AsyncMock(), _token="lielielie", _webhook_id=hikari.Snowflake(123342)
        )

        assert str(link) == "https://discord.com/api/webhooks/123342/lielielie"

    @pytest.mark.asyncio()
    async def test_fetch_webhook(self):
        mock_app = mock.AsyncMock()
        mock_app.rest.fetch_webhook.return_value = mock.Mock(hikari.IncomingWebhook)
        link = yuyo.links.WebhookLink(  # noqa: S106
            _app=mock_app, _token="I'm the one to blame", _webhook_id=hikari.Snowflake(654345)
        )

        result = await link.fetch_webhook()

        assert result is mock_app.rest.fetch_webhook.return_value
        mock_app.rest.fetch_webhook.assert_awaited_once_with(654345, token="I'm the one to blame")  # noqa: S106


def test_make_oauth_link():
    link = yuyo.links.make_oauth_link(652312, [hikari.OAuth2Scope.EMAIL, hikari.OAuth2Scope.IDENTIFY])

    assert link == "https://discord.com/api/oauth2/authorize?client_id=652312&scope=email+identify"


def test_make_oauth_link_with_optional_cnfig():
    link = yuyo.links.make_oauth_link(
        675345123,
        [hikari.OAuth2Scope.CONNECTIONS],
        disable_guild_select=True,
        guild=123543123,
        permissions=5431,
        prompt="consent",
        redirect_uri="https://example.com/yeet-my-girl",
        response_type="code",
        state="Washington DC",
    )

    assert link == (
        "https://discord.com/api/oauth2/authorize?client_id=675345123&scope=connections&disable_guild_select=true&"
        "guild_id=123543123&permissions=5431&prompt=consent&redirect_uri=https%3A%2F%2Fexample.com%2Fyeet-my-girl&"
        "response_type=code&state=Washington+DC"
    )


def test_make_oauth_link_with_unique_objects():
    application = hikari.PartialApplication(id=hikari.Snowflake(876234123), name="", description="", icon_hash="")
    guild = hikari.PartialGuild(app=mock.AsyncMock(), id=hikari.Snowflake(453123312), icon_hash="", name="")
    link = yuyo.links.make_oauth_link(
        application, [hikari.OAuth2Scope.RPC, hikari.OAuth2Scope.APPLICATIONS_BUILDS_UPLOAD], guild=guild
    )

    assert (
        link
        == "https://discord.com/api/oauth2/authorize?client_id=876234123&scope=rpc+applications.builds.upload&guild_id=453123312"
    )


def test_make_bot_invite():
    link = yuyo.links.make_bot_invite(54123)

    assert link == "https://discord.com/api/oauth2/authorize?client_id=54123&scope=bot&permissions=0"


def test_make_bot_invite_with_optional_config():
    link = yuyo.links.make_bot_invite(4532234, disable_guild_select=True, guild=654123, permissions=234)

    assert link == (
        "https://discord.com/api/oauth2/authorize?client_id=4532234&"
        "scope=bot&disable_guild_select=true&guild_id=654123&permissions=234"
    )


def test_make_bot_invite_when_permissions_is_none():
    link = yuyo.links.make_bot_invite(65123123, permissions=None)

    assert link == "https://discord.com/api/oauth2/authorize?client_id=65123123&scope=bot"


def test_make_bot_invite_with_unique_objects():
    application = hikari.PartialApplication(id=hikari.Snowflake(7683452), name="", description="", icon_hash="")
    guild = hikari.PartialGuild(app=mock.AsyncMock(), id=hikari.Snowflake(562341), icon_hash="", name="")
    link = yuyo.links.make_bot_invite(application, guild=guild)

    assert link == "https://discord.com/api/oauth2/authorize?client_id=7683452&scope=bot&guild_id=562341&permissions=0"
