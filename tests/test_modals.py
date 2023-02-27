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
# pyright: reportPrivateUsage=none
# This leads to too many false-positives around mocks.

import datetime
from unittest import mock

import alluka
import freezegun
import hikari
import pytest

from yuyo import modals

try:
    import tanjun

except ModuleNotFoundError:
    tanjun = None


class TestBasicTimeout:
    def test_has_expired(self):
        with freezegun.freeze_time() as frozen:
            timeout = modals.BasicTimeout(datetime.timedelta(seconds=60), max_uses=4)

            for tick_time in [15, 15, 15, 14]:
                frozen.tick(datetime.timedelta(seconds=tick_time))
                assert timeout.has_expired is False

            frozen.tick(datetime.timedelta(seconds=2))
            assert timeout.has_expired is True

    def test_has_expired_when_no_uses_left(self):
        timeout = modals.BasicTimeout(datetime.timedelta(days=6000), max_uses=1)

        assert timeout.increment_uses() is True
        assert timeout.has_expired is True

        assert timeout.has_expired is True

    def test_increment_uses(self):
        timeout = modals.BasicTimeout(datetime.timedelta(days=6000), max_uses=4)

        assert timeout.increment_uses() is False
        assert timeout.has_expired is False

        assert timeout.increment_uses() is False
        assert timeout.has_expired is False

        assert timeout.increment_uses() is False
        assert timeout.has_expired is False

        assert timeout.increment_uses() is True
        assert timeout.has_expired is True

        assert timeout.has_expired is True

    def test_increment_uses_when_unlimited(self):
        timeout = modals.BasicTimeout(datetime.timedelta(days=6000), max_uses=-1)

        for _ in range(0, 10000):
            assert timeout.increment_uses() is False

    def test_increment_uses_when_already_expired(self):
        timeout = modals.BasicTimeout(datetime.timedelta(days=6000), max_uses=1)

        assert timeout.increment_uses() is True
        assert timeout.has_expired is True

        with pytest.raises(RuntimeError, match="Uses already depleted"):
            timeout.increment_uses()


class TestNeverTimeout:
    def test_has_expired(self):
        assert modals.NeverTimeout().has_expired is False

    def test_increment_uses(self):
        timeout = modals.NeverTimeout()

        for _ in range(0, 10000):
            assert timeout.increment_uses() is False


class TestModalContext:
    def test_client_property(self):
        mock_client = mock.Mock()
        context = modals.ModalContext(mock_client, mock.Mock(), mock.Mock())

        assert context.client is mock_client

    @pytest.mark.skip(reason="TODO")
    async def test_create_initial_response(self):
        ...

    @pytest.mark.skip(reason="TODO")
    async def test_defer(self):
        ...


class TestModalClient:
    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_context_manager(self):
        ...

    def test_alluka_property(self):
        client = modals.ModalClient()

        assert isinstance(client.alluka, alluka.Client)
        assert client.alluka.get_type_dependency(modals.ModalClient) is client

    def test_alluka_property_when_passed_through(self):
        mock_alluka = mock.Mock()
        client = modals.ModalClient(alluka=mock_alluka)

        assert client.alluka is mock_alluka
        mock_alluka.set_type_dependency.assert_not_called()

    @pytest.mark.skip(reason="TODO")
    def test_from_gateway_bot(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_from_rest_bot(self):
        ...

    @pytest.mark.skipif(tanjun is None, reason="Tanjun specific test")
    @pytest.mark.skip(reason="TODO")
    def test_from_tanjun(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_from_rest_bot_when_bot_managed(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test__remove_task(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test__add_task(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test__on_starting(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test__on_stopping(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test__gc(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_close(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_open(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_gateway_event_for_other_interaction_type(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_gateway_event_for_prefix_match(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_gateway_event_for_expired_prefix_match(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_gateway_event_for_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_gateway_event_for_expired_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_gateway_event_for_modal_after_expired_prefix_match(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_gateway_event_for_expired_modal_and_prefix(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_rest_request_for_prefix_match(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_rest_request_for_expired_prefix_match(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_rest_request_for_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_rest_request_for_expired_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_rest_request_for_modal_after_expired_prefix_match(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_rest_request_for_expired_modal_and_prefix(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_set_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_set_modal_for_prefix_match(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_set_modal_when_custom_id_already_registered(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_set_modal_when_custom_id_already_registered_as_prefix(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_set_modal_when_no_timeout_set(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_set_modal_when_timeout_is_none(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_get_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_get_modal_for_prefix(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_get_modal_when_not_registered(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_remove_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_remove_modal_for_prefix(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_remove_modal_when_not_registered(self):
        ...


@pytest.mark.skip(reason="TODO")
class TestModal:
    def test_subclassing_behaviour(self):
        ...

    def test_subclassing_behaviour_for_multiple_inheritance(self):
        ...

    def test_add_static_text_input(self):
        ...

    def test_add_static_text_input_with_optional_fields(self):
        ...

    def test_static_text_input(self):
        ...

    def test_static_text_input_with_optional_fields(self):
        ...

    @pytest.mark.asyncio()
    async def test_execute(self):
        ...

    @pytest.mark.asyncio()
    async def test_execute_for_prefix_match(self):
        ...

    @pytest.mark.asyncio()
    async def test_execute_when_missing_default_for_a_field(self):
        ...

    @pytest.mark.asyncio()
    async def test_execute_when_field_type_mismatch(self):
        ...

    @pytest.mark.asyncio()
    async def test_execute_when_field_defaults(self):
        ...


@pytest.mark.asyncio()
async def test_modal():
    mock_ctx = mock.Mock()
    mock_callback = mock.AsyncMock()

    async def callback(ctx: modals.ModalContext, value: int, /, *, other: str) -> None:
        return await mock_callback(ctx, value, other=other)

    modal = modals.modal(callback, ephemeral_default=True)

    assert isinstance(modal, modals.Modal)
    assert modal._ephemeral_default is True

    result = await modal.callback(mock_ctx, 123, other="543")
    assert result is mock_callback.return_value
    mock_callback.assert_awaited_once_with(mock_ctx, 123, other="543")


@pytest.mark.asyncio()
async def test_modal_with_defaults():
    mock_ctx = mock.Mock()
    mock_callback = mock.AsyncMock()

    async def callback(ctx: modals.ModalContext, meow: str, /, *, nyaa: str) -> None:
        return await mock_callback(ctx, meow, nyaa=nyaa)

    modal = modals.modal(callback)

    assert isinstance(modal, modals.Modal)
    assert modal._ephemeral_default is False

    result = await modal.callback(mock_ctx, "432", nyaa="3234")
    assert result is mock_callback.return_value
    mock_callback.assert_awaited_once_with(mock_ctx, "432", nyaa="3234")


@pytest.mark.asyncio()
async def test_as_modal():
    mock_ctx = mock.Mock()
    mock_callback = mock.AsyncMock()

    async def callback(ctx: modals.ModalContext, of: int, /, *, accused: int) -> None:
        return await mock_callback(ctx, of, accused=accused)

    modal = modals.as_modal(ephemeral_default=True)(callback)

    assert isinstance(modal, modals.Modal)
    assert modal._ephemeral_default is True

    result = await modal.callback(mock_ctx, 123, accused=54444)
    assert result is mock_callback.return_value
    mock_callback.assert_awaited_once_with(mock_ctx, 123, accused=54444)


@pytest.mark.asyncio()
async def test_as_modal_with_defaults():
    mock_ctx = mock.Mock()
    mock_callback = mock.AsyncMock()

    async def callback(ctx: modals.ModalContext, up: bool, /, *, echo: bytes) -> None:
        return await mock_callback(ctx, up, echo=echo)

    modal = modals.as_modal(ephemeral_default=True)(callback)

    assert isinstance(modal, modals.Modal)
    assert modal._ephemeral_default is True

    result = await modal.callback(mock_ctx, True, echo=b"fdsasda")
    assert result is mock_callback.return_value
    mock_callback.assert_awaited_once_with(mock_ctx, True, echo=b"fdsasda")


@pytest.mark.asyncio()
async def test_as_modal_with_defaults_when_no_parameters_supplied():
    mock_ctx = mock.Mock()
    mock_callback = mock.AsyncMock()

    async def callback(ctx: modals.ModalContext, value: bytes, /, *, other: bytes) -> None:
        return await mock_callback(ctx, value, other=other)

    modal = modals.as_modal(callback)

    assert isinstance(modal, modals.Modal)
    assert modal._ephemeral_default is False

    result = await modal.callback(mock_ctx, b"true", other=b"dfsaasd")
    assert result is mock_callback.return_value
    mock_callback.assert_awaited_once_with(mock_ctx, b"true", other=b"dfsaasd")


@pytest.mark.asyncio()
async def test_as_modal_template():
    mock_callback = mock.AsyncMock()
    mock_ctx = mock.Mock()

    async def callback(ctx: modals.ModalContext, user: int, /, *, other: str) -> None:
        return await mock_callback(ctx, user, other=other)

    modal_cls = modals.as_modal_template(ephemeral_default=True)(callback)

    assert issubclass(modal_cls, modals.Modal)
    modal = modal_cls()
    assert isinstance(modal, modals.Modal)
    assert modal._ephemeral_default is True

    result = await modal.callback(mock_ctx, 123, other="hi")
    assert result is mock_callback.return_value
    mock_callback.assert_awaited_once_with(mock_ctx, 123, other="hi")


@pytest.mark.asyncio()
async def test_as_modal_template_with_defaults():
    mock_callback = mock.AsyncMock()
    mock_ctx = mock.Mock()

    async def callback(ctx: modals.ModalContext, member: str, /, *, none: bool) -> None:
        return await mock_callback(ctx, member, none=none)

    modal_cls = modals.as_modal_template(callback)

    assert issubclass(modal_cls, modals.Modal)
    modal = modal_cls()
    assert isinstance(modal, modals.Modal)
    assert modal._ephemeral_default is False

    result = await modal.callback(mock_ctx, "these days it's", none=True)
    assert result is mock_callback.return_value
    mock_callback.assert_awaited_once_with(mock_ctx, "these days it's", none=True)


@pytest.mark.asyncio()
async def test_as_modal_template_when_config_overriden_in_init_call():
    mock_callback = mock.AsyncMock()
    mock_ctx = mock.Mock()

    async def callback(ctx: modals.ModalContext, thing: str, /, *, other_thing: str) -> None:
        return await mock_callback(ctx, thing, other_thing=other_thing)

    modal_cls = modals.as_modal_template(ephemeral_default=True)(callback)

    assert issubclass(modal_cls, modals.Modal)
    modal = modal_cls(ephemeral_default=False)
    assert isinstance(modal, modals.Modal)
    assert modal._ephemeral_default is False

    result = await modal.callback(mock_ctx, "why don't we", other_thing="keep it coming back")
    assert result is mock_callback.return_value
    mock_callback.assert_awaited_once_with(mock_ctx, "why don't we", other_thing="keep it coming back")


def test_with_static_text_input():
    modal_cls = modals.as_modal_template(mock.Mock())
    modal_cls.add_static_text_input = mock.Mock()

    result = modals.with_static_text_input("meow")(modal_cls)

    assert result is modal_cls.add_static_text_input.return_value
    modal_cls.add_static_text_input.assert_called_once_with(
        "meow",
        custom_id=None,
        style=hikari.TextInputStyle.SHORT,
        placeholder=hikari.UNDEFINED,
        value=hikari.UNDEFINED,
        default=modals.NO_DEFAULT,
        min_length=0,
        max_length=4000,
        prefix_match=False,
        parameter=None,
    )


def test_with_static_text_input_with_defaults():
    modal_cls = modals.as_modal_template(mock.Mock())
    modal_cls.add_static_text_input = mock.Mock()

    result = modals.with_static_text_input(
        "meow",
        custom_id="echo",
        style=hikari.TextInputStyle.PARAGRAPH,
        placeholder="e",
        value="x",
        default=123,
        min_length=50,
        max_length=70,
        prefix_match=True,
        parameter="param",
    )(modal_cls)

    assert result is modal_cls.add_static_text_input.return_value
    modal_cls.add_static_text_input.assert_called_once_with(
        "meow",
        custom_id="echo",
        style=hikari.TextInputStyle.PARAGRAPH,
        placeholder="e",
        value="x",
        default=123,
        min_length=50,
        max_length=70,
        prefix_match=True,
        parameter="param",
    )


def test_with_text_input():
    mock_add_text_input = mock.Mock()
    modal_cls = modals.as_modal_template(mock.Mock())
    modal_cls.add_text_input = mock_add_text_input
    modal = modal_cls()

    result = modals.with_text_input("nyaa")(modal)

    assert result is modal_cls.add_text_input.return_value
    mock_add_text_input.assert_called_once_with(
        "nyaa",
        custom_id=None,
        style=hikari.TextInputStyle.SHORT,
        placeholder=hikari.UNDEFINED,
        value=hikari.UNDEFINED,
        default=modals.NO_DEFAULT,
        min_length=0,
        max_length=4000,
        prefix_match=False,
        parameter=None,
    )


def test_with_text_input_with_defaults():
    mock_add_text_input = mock.Mock()
    modal_cls = modals.as_modal_template(mock.Mock())
    modal_cls.add_text_input = mock_add_text_input
    modal = modal_cls()

    result = modals.with_text_input(
        "nyaa",
        custom_id="bridge",
        style=hikari.TextInputStyle.PARAGRAPH,
        placeholder="place",
        value="you",
        default="superman",
        min_length=6,
        max_length=9,
        prefix_match=True,
        parameter="arg",
    )(modal)

    assert result is mock_add_text_input.return_value
    mock_add_text_input.assert_called_once_with(
        "nyaa",
        custom_id="bridge",
        style=hikari.TextInputStyle.PARAGRAPH,
        placeholder="place",
        value="you",
        default="superman",
        min_length=6,
        max_length=9,
        prefix_match=True,
        parameter="arg",
    )
