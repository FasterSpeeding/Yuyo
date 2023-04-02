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

import typing
from unittest import mock

import alluka
import hikari
import pytest

from yuyo import modals

try:
    import tanjun

except ModuleNotFoundError:
    tanjun = None


class TestModalContext:
    def test_client_property(self):
        mock_client = mock.Mock()
        context = modals.ModalContext(mock_client, mock.Mock(), "", "", {}, mock.Mock())

        assert context.client is mock_client

    def test_component_ids_property(self):
        components = {"id": "meow"}
        context = modals.ModalContext(mock.Mock(), mock.Mock(), "", "", components, mock.Mock())

        assert context.component_ids is components

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
    async def test_on_gateway_event_for_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_on_gateway_event_for_expired_modal(self):
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
    def test_set_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_set_modal_when_custom_id_already_registered(self):
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
    def test_get_modal_when_not_registered(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_remove_modal(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_remove_modal_when_not_registered(self):
        ...


class TestModal:
    @pytest.mark.skip(reason="TODO")
    def test_subclassing_behaviour(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_subclassing_behaviour_for_multiple_inheritance(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_add_static_text_input(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_add_static_text_input_with_optional_fields(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_static_text_input(self):
        ...

    @pytest.mark.skip(reason="TODO")
    def test_static_text_input_with_optional_fields(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_execute(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_execute_when_missing_default_for_a_field(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_execute_when_field_type_mismatch(self):
        ...

    @pytest.mark.skip(reason="TODO")
    @pytest.mark.asyncio()
    async def test_execute_when_field_defaults(self):
        ...

    def test_with_text_input_descriptor(self):
        @modals.as_modal_template()
        async def modal_template(
            ctx: modals.ModalContext,
            a_field: typing.Union[str, int] = modals.text_input(
                "bababooi",
                custom_id="yeet:me",
                style=hikari.TextInputStyle.PARAGRAPH,
                placeholder="place deez",
                value="boom",
                default=123,
                min_length=43,
                max_length=222,
            ),
        ) -> None:
            ...

        modal = modal_template()

        assert len(modal.rows) == 1
        row = modal.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "bababooi"
        assert component.custom_id == "yeet:me"
        assert component.style is hikari.TextInputStyle.PARAGRAPH
        assert component.placeholder == "place deez"
        assert component.value == "boom"
        assert component.is_required is False
        assert component.min_length == 43
        assert component.max_length == 222

        assert len(modal._tracked_fields) == 1
        field = modal._tracked_fields[0]
        assert isinstance(field, modals._TrackedField)
        assert field.id_match == "yeet"
        assert field.default == 123
        assert field.parameter == "a_field"
        assert field.type is hikari.ComponentType.TEXT_INPUT

    @pytest.mark.parametrize("default", ["meep", "x" * 4000, "a"])
    def test_with_text_input_descriptor_uses_string_default_as_value(self, default: str):
        @modals.as_modal_template()
        async def modal_template(
            ctx: modals.ModalContext, a_field: typing.Union[str, int] = modals.text_input("bababooi", default=default)
        ) -> None:
            ...

        modal = modal_template()

        assert len(modal.rows) == 1
        row = modal.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.value == default
        assert component.is_required is False

        assert len(modal._tracked_fields) == 1
        field = modal._tracked_fields[0]
        assert isinstance(field, modals._TrackedField)
        assert field.default == default

    def test_with_text_input_descriptor_with_non_str_default(self):
        @modals.as_modal_template()
        async def modal_template(
            ctx: modals.ModalContext, a_field: typing.Union[str, int] = modals.text_input("bababooi", default=123)
        ) -> None:
            ...

        modal = modal_template()

        assert len(modal.rows) == 1
        row = modal.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.value is hikari.UNDEFINED
        assert component.is_required is False

        assert len(modal._tracked_fields) == 1
        field = modal._tracked_fields[0]
        assert isinstance(field, modals._TrackedField)
        assert field.default == 123

    def test_with_text_input_descriptor_when_string_default_over_4000_chars(self):
        @modals.as_modal_template()
        async def modal_template(
            ctx: modals.ModalContext,
            a_field: typing.Union[str, int] = modals.text_input("bababooi", default="x" * 4001),
        ) -> None:
            ...

        modal = modal_template()

        assert len(modal.rows) == 1
        row = modal.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.value is hikari.UNDEFINED
        assert component.is_required is False

        assert len(modal._tracked_fields) == 1
        field = modal._tracked_fields[0]
        assert isinstance(field, modals._TrackedField)
        assert field.default == "x" * 4001

    def test_with_text_input_descriptor_with_defaults(self):
        @modals.as_modal_template()
        async def modal_template(ctx: modals.ModalContext, b_field: str = modals.text_input("eaaaaaaa")) -> None:
            ...

        modal = modal_template()

        assert len(modal.rows) == 1
        row = modal.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "eaaaaaaa"
        assert isinstance(component.custom_id, str)
        custom_id_1 = component.custom_id
        assert component.style is hikari.TextInputStyle.SHORT
        assert component.placeholder is hikari.UNDEFINED
        assert component.value is hikari.UNDEFINED
        assert component.is_required is True
        assert component.min_length == 0
        assert component.max_length == 4000

        assert len(modal._tracked_fields) == 1
        field = modal._tracked_fields[0]
        assert isinstance(field, modals._TrackedField)
        assert field.id_match == custom_id_1
        assert field.default is modals.NO_DEFAULT
        assert field.parameter == "b_field"
        assert field.type is hikari.ComponentType.TEXT_INPUT

    def test_handles_overflowing_text_input_descriptor(self):
        @modals.as_modal_template
        async def modal_template(
            ctx: modals.ModalContext,
            field_1: str = modals.text_input("erwe"),
            field_2: str = modals.text_input("sdfsd"),
        ) -> None:
            ...

        modal = modal_template()

        assert len(modal.rows) == 2
        row = modal.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "erwe"

        row = modal.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "sdfsd"

    def test_with_text_modals_options_class(self):
        class ModalOptions(modals.ModalOptions):
            fieldy: str = modals.text_input("fieldy")
            meowy: typing.Union[str, None] = modals.text_input(
                "x3",
                custom_id="nyeep",
                style=hikari.TextInputStyle.PARAGRAPH,
                placeholder="e",
                value="aaaaa",
                default=None,
                min_length=4,
                max_length=421,
            )

        @modals.as_modal_template
        async def modal_template(ctx: modals.ModalContext, options: ModalOptions) -> None:
            ...

        modal = modal_template()

        assert len(modal.rows) == 2
        row = modal.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "fieldy"
        assert isinstance(component.custom_id, str)
        custom_id_1 = component.custom_id
        assert component.style is hikari.TextInputStyle.SHORT
        assert component.placeholder is hikari.UNDEFINED
        assert component.value is hikari.UNDEFINED
        assert component.is_required is True
        assert component.min_length == 0
        assert component.max_length == 4000

        row = modal.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "x3"
        assert component.custom_id == "nyeep"
        assert component.style is hikari.TextInputStyle.PARAGRAPH
        assert component.placeholder == "e"
        assert component.value == "aaaaa"
        assert component.is_required is False
        assert component.min_length == 4
        assert component.max_length == 421

        assert len(modal._tracked_fields) == 1
        tracked = modal._tracked_fields[0]
        assert isinstance(tracked, modals._TrackedDataclass)
        assert tracked._dataclass is ModalOptions
        assert tracked.parameter == "options"

        assert len(tracked._fields) == 2
        field = tracked._fields[0]
        assert isinstance(field, modals._TrackedField)
        assert field.id_match == custom_id_1
        assert field.default is modals.NO_DEFAULT
        assert field.parameter == "fieldy"
        assert field.type is hikari.ComponentType.TEXT_INPUT

        field = tracked._fields[1]
        assert isinstance(field, modals._TrackedField)
        assert field.id_match == "nyeep"
        assert field.default is None
        assert field.parameter == "meowy"
        assert field.type is hikari.ComponentType.TEXT_INPUT

    def test_with_text_modals_options_class_handles_inheritance(self):
        class ModalOptions(modals.ModalOptions):
            fieldy: str = modals.text_input("field")

        class MiddleModalOptions(ModalOptions):
            meowy: str = modals.text_input("meow")

        class FinalModalOptions(MiddleModalOptions):
            booy: str = modals.text_input("bababooi")

        @modals.as_modal_template
        async def modal_template(ctx: modals.ModalContext, banana: FinalModalOptions) -> None:
            ...

        modal = modal_template()

        assert len(modal.rows) == 3
        row = modal.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "field"
        custom_id_1 = component.custom_id

        row = modal.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "meow"
        custom_id_2 = component.custom_id

        row = modal.rows[2]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "bababooi"
        custom_id_3 = component.custom_id

        assert len(modal._tracked_fields) == 1
        tracked = modal._tracked_fields[0]
        assert isinstance(tracked, modals._TrackedDataclass)
        assert tracked._dataclass is FinalModalOptions
        assert tracked.parameter == "banana"

        assert len(tracked._fields) == 3
        field = tracked._fields[0]
        assert isinstance(field, modals._TrackedField)
        assert field.parameter == "fieldy"
        assert field.id_match == custom_id_1

        field = tracked._fields[1]
        assert isinstance(field, modals._TrackedField)
        assert field.parameter == "meowy"
        assert field.id_match == custom_id_2

        field = tracked._fields[2]
        assert isinstance(field, modals._TrackedField)
        assert field.parameter == "booy"
        assert field.id_match == custom_id_3

    def test_with_text_modals_options_class_handles_mixed_inheritance(self):
        class ModalOptions(modals.ModalOptions):
            fallen: str = modals.text_input("flat")

        class OtherModalOptions(modals.ModalOptions):
            felen: str = modals.text_input("hihi")
            patman: str = modals.text_input("pat me")

        class Both(ModalOptions, OtherModalOptions):
            me: str = modals.text_input("ow")

        @modals.as_modal_template
        async def modal_template(ctx: modals.ModalContext, extra: Both) -> None:
            ...

        modal = modal_template()

        assert len(modal.rows) == 4
        row = modal.rows[0]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "flat"
        custom_id_1 = component.custom_id

        row = modal.rows[1]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "hihi"
        custom_id_2 = component.custom_id

        row = modal.rows[2]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "pat me"
        custom_id_3 = component.custom_id

        row = modal.rows[3]
        assert len(row.components) == 1
        component = row.components[0]
        assert isinstance(component, hikari.api.TextInputBuilder)
        assert component.label == "ow"
        custom_id_4 = component.custom_id

        row = modal.rows[0]
        assert len(row.components) == 1

        assert len(modal._tracked_fields) == 1
        tracked = modal._tracked_fields[0]
        assert isinstance(tracked, modals._TrackedDataclass)
        assert tracked._dataclass is Both
        assert tracked.parameter == "extra"

        assert len(tracked._fields) == 4
        field = tracked._fields[0]
        assert isinstance(field, modals._TrackedField)
        assert field.parameter == "fallen"
        assert field.id_match == custom_id_1

        field = tracked._fields[1]
        assert isinstance(field, modals._TrackedField)
        assert field.parameter == "felen"
        assert field.id_match == custom_id_2

        field = tracked._fields[2]
        assert isinstance(field, modals._TrackedField)
        assert field.parameter == "patman"
        assert field.id_match == custom_id_3

        field = tracked._fields[3]
        assert isinstance(field, modals._TrackedField)
        assert field.parameter == "me"
        assert field.id_match == custom_id_4


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
        parameter="arg",
    )
