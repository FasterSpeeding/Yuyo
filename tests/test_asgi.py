# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020-2021, Faster Speeding
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
import traceback
from unittest import mock

import asgiref.typing
import hikari
import pytest

import yuyo


class TestAsgiAdapter:
    @pytest.fixture()
    def stub_server(self) -> hikari.api.InteractionServer:
        return mock.AsyncMock()

    @pytest.fixture()
    def adapter(self, stub_server: hikari.api.InteractionServer) -> yuyo.AsgiAdapter:
        return yuyo.AsgiAdapter(stub_server)

    def test_server_property(self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer) -> None:
        assert adapter.server is stub_server

    @pytest.fixture()
    def http_scope(self) -> asgiref.typing.HTTPScope:
        return asgiref.typing.HTTPScope(
            type="http",
            asgi=asgiref.typing.ASGIVersions(spec_version="ok", version="3.0"),
            http_version="1.1",
            method="POST",
            scheme="",
            path="/",
            raw_path=b"",
            headers=[],
            client=("", 1),
            server=("", 1),
            extensions=None,
            query_string=b"",
            root_path="",
        )

    @pytest.mark.asyncio()
    async def test___call___when_http(
        self, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ) -> None:
        mock_process_request = mock.AsyncMock()
        mock_receive = mock.Mock()
        mock_send = mock.Mock()

        class StubAdapter(yuyo.AsgiAdapter):
            process_request = mock_process_request

        stub_adapter = StubAdapter(stub_server)

        await stub_adapter(http_scope, mock_receive, mock_send)

        mock_process_request.assert_awaited_once_with(http_scope, mock_receive, mock_send)

    @pytest.mark.asyncio()
    async def test___call___when_lifespan(self, stub_server: hikari.api.InteractionServer):
        mock_process_lifespan_event = mock.AsyncMock()
        mock_receive = mock.Mock()
        mock_send = mock.Mock()
        mock_scope = asgiref.typing.LifespanScope(
            type="lifespan", asgi=asgiref.typing.ASGIVersions(spec_version="ok", version="3.0")
        )

        class StubAdapter(yuyo.AsgiAdapter):
            process_lifespan_event = mock_process_lifespan_event

        stub_adapter = StubAdapter(stub_server)

        await stub_adapter(mock_scope, mock_receive, mock_send)

        mock_process_lifespan_event.assert_awaited_once_with(mock_receive, mock_send)

    @pytest.mark.asyncio()
    async def test___call___when_webhook(self, adapter: yuyo.AsgiAdapter):
        with pytest.raises(NotImplementedError, match="Websocket operations are not supported"):
            await adapter(
                asgiref.typing.WebSocketScope(
                    type="websocket",
                    asgi=asgiref.typing.ASGIVersions(spec_version="ok", version="3.0"),
                    http_version="...",
                    scheme="...",
                    path="/",
                    raw_path=b"",
                    query_string=b"",
                    root_path="",
                    headers=[],
                    client=("2", 2),
                    server=None,
                    subprotocols=[],
                    extensions={},
                ),
                mock.AsyncMock(),
                mock.AsyncMock(),
            )

    @pytest.mark.asyncio()
    async def test_process_lifespan_event_on_startup(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.startup"})
        mock_send = mock.AsyncMock()

        await adapter.process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.startup.complete"})

    @pytest.mark.asyncio()
    async def test_process_lifespan_event_on_startup_with_callbacks(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.startup"})
        mock_send = mock.AsyncMock()
        mock_async_callback = mock.AsyncMock()
        mock_callback = mock.Mock()
        adapter.add_startup_callback(mock_async_callback).add_startup_callback(mock_callback)

        await adapter.process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_async_callback.assert_awaited_once_with()
        mock_callback.assert_called_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.startup.complete"})

    @pytest.mark.asyncio()
    async def test_process_lifespan_event_on_startup_when_sync_callback_fails(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.startup"})
        mock_send = mock.AsyncMock()
        mock_async_callback = mock.AsyncMock(side_effect=Exception("test"))
        mock_callback = mock.Mock()
        adapter.add_startup_callback(mock_async_callback).add_startup_callback(mock_callback)

        with mock.patch.object(traceback, "format_exc") as format_exc:
            await adapter.process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_async_callback.assert_awaited_once_with()
        mock_callback.assert_called_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.startup.failed", "message": format_exc.return_value})
        format_exc.assert_called_once_with()

    @pytest.mark.asyncio()
    async def test_process_lifespan_event_on_startup_when_async_callback_fails(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.startup"})
        mock_send = mock.AsyncMock()
        mock_async_callback = mock.AsyncMock()
        mock_callback = mock.Mock(side_effect=Exception("test"))
        adapter.add_startup_callback(mock_async_callback).add_startup_callback(mock_callback)

        with mock.patch.object(traceback, "format_exc") as format_exc:
            await adapter.process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_async_callback.assert_awaited_once_with()
        mock_callback.assert_called_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.startup.failed", "message": format_exc.return_value})
        format_exc.assert_called_once_with()

    @pytest.mark.asyncio()
    async def test_process_lifespan_event_on_shutdown(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.shutdown"})
        mock_send = mock.AsyncMock()

        await adapter.process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.shutdown.complete"})

    @pytest.mark.asyncio()
    async def test_process_lifespan_event_on_shutdown_with_callbacks(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.shutdown"})
        mock_send = mock.AsyncMock()
        mock_async_callback = mock.AsyncMock()
        mock_callback = mock.Mock()
        adapter.add_shutdown_callback(mock_async_callback).add_shutdown_callback(mock_callback)

        await adapter.process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_async_callback.assert_awaited_once_with()
        mock_callback.assert_called_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.shutdown.complete"})

    @pytest.mark.asyncio()
    async def test_process_lifespan_event_on_shutdown_when_sync_callback_fails(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.shutdown"})
        mock_send = mock.AsyncMock()
        mock_async_callback = mock.AsyncMock(side_effect=Exception("test"))
        mock_callback = mock.Mock()
        adapter.add_shutdown_callback(mock_async_callback).add_shutdown_callback(mock_callback)

        with mock.patch.object(traceback, "format_exc") as format_exc:
            await adapter.process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_async_callback.assert_awaited_once_with()
        mock_callback.assert_called_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.shutdown.failed", "message": format_exc.return_value})
        format_exc.assert_called_once_with()

    @pytest.mark.asyncio()
    async def test_process_lifespan_event_on_shutdown_when_async_callback_fails(
        self, adapter: yuyo.AsgiAdapter
    ) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.shutdown"})
        mock_send = mock.AsyncMock()
        mock_async_callback = mock.AsyncMock()
        mock_callback = mock.Mock(side_effect=Exception("test"))
        adapter.add_shutdown_callback(mock_async_callback).add_shutdown_callback(mock_callback)

        with mock.patch.object(traceback, "format_exc") as format_exc:
            await adapter.process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_async_callback.assert_awaited_once_with()
        mock_callback.assert_called_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.shutdown.failed", "message": format_exc.return_value})
        format_exc.assert_called_once_with()

    @pytest.mark.asyncio()
    async def test_process_lifespan_event_on_invalid_lifespan_type(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.idk"})
        mock_send = mock.AsyncMock()

        with pytest.raises(RuntimeError, match="Unknown lifespan event lifespan.idk"):
            await adapter.process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_send.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"Content-Type", b"application/json"),
            (b"x-signature-timestamp", b"321123"),
            (b"random-header2", b"random value"),
            (b"x-signature-ed25519", b"6e796161"),
            (b"random-header", b"random value"),
        ]
        mock_receive = mock.AsyncMock(
            side_effect=[{"body": b"cat", "more_body": True}, {"body": b"girls", "more_body": False}]
        )
        mock_send = mock.AsyncMock()
        stub_server.on_interaction.return_value.headers = {
            "Content-Type": "jazz hands",
            "kill": "me baby",
            "I am the milk man": "my milk is delicious",
            "and the sea shall run white": "with his rage",
        }

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": stub_server.on_interaction.return_value.status_code,
                        "headers": [
                            (b"Content-Type", b"jazz hands"),
                            (b"kill", b"me baby"),
                            (b"I am the milk man", b"my milk is delicious"),
                            (b"and the sea shall run white", b"with his rage"),
                        ],
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": stub_server.on_interaction.return_value.payload,
                        "more_body": False,
                    }
                ),
            ]
        )
        mock_receive.assert_has_awaits([mock.call(), mock.call()])
        stub_server.on_interaction.assert_awaited_once_with(bytearray(b"catgirls"), b"nyaa", b"321123")

    @pytest.mark.asyncio()
    async def test_process_request_when_not_post(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["method"] = "GET"
        http_scope["path"] = "/"
        mock_receive = mock.AsyncMock()
        mock_send = mock.AsyncMock()

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 404,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"Not found", "more_body": False}),
            ]
        )
        mock_receive.assert_not_called()
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request_when_not_base_route(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["method"] = "POST"
        http_scope["path"] = "/not-base-route"
        mock_receive = mock.AsyncMock()
        mock_send = mock.AsyncMock()

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 404,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"Not found", "more_body": False}),
            ]
        )
        mock_receive.assert_not_called()
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request_when_no_body(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        mock_receive = mock.AsyncMock(return_value={"body": b"", "more_body": False})
        mock_send = mock.AsyncMock()

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"POST request must have a body", "more_body": False}),
            ]
        )
        mock_receive.assert_awaited_once_with()
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request_when_no_body_and_receive_empty(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        mock_receive = mock.AsyncMock(return_value={})
        mock_send = mock.AsyncMock()

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"POST request must have a body", "more_body": False}),
            ]
        )
        mock_receive.assert_awaited_once_with()
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request_when_no_content_type(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = []
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call(
                    {"type": "http.response.body", "body": b"Content-Type must be application/json", "more_body": False}
                ),
            ]
        )
        mock_receive.assert_awaited_once_with()
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request_when_not_json_content_type(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [(b"Content-Type", b"NOT JSON")]
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call(
                    {"type": "http.response.body", "body": b"Content-Type must be application/json", "more_body": False}
                ),
            ]
        )
        mock_receive.assert_awaited_once_with()
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request_when_missing_timestamp_header(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [(b"Content-Type", b"application/json"), (b"x-signature-ed25519", b"676179")]
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": b"Missing required request signature header(s)",
                        "more_body": False,
                    }
                ),
            ]
        )
        mock_receive.assert_awaited_once_with()
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request_when_missing_ed25519_header(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [(b"Content-Type", b"application/json"), (b"x-signature-timestamp", b"87")]
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": b"Missing required request signature header(s)",
                        "more_body": False,
                    }
                ),
            ]
        )
        mock_receive.assert_awaited_once_with()
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request_when_ed_25519_header_not_valid(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"Content-Type", b"application/json"),
            (b"x-signature-timestamp", b"87"),
            (b"x-signature-ed25519", "🇯🇵".encode()),
        ]
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": b"Invalid ED25519 signature header found",
                        "more_body": False,
                    }
                ),
            ]
        )
        mock_receive.assert_awaited_once_with()
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test_process_request_when_on_interaction_raises(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"x-signature-timestamp", b"653245"),
            (b"random-header2", b"random value"),
            (b"x-signature-ed25519", b"7472616e73"),
            (b"random-header", b"random value"),
            (b"Content-Type", b"application/json"),
        ]
        mock_receive = mock.AsyncMock(return_value={"body": b"transive", "more_body": False})
        mock_send = mock.AsyncMock()
        stub_error = Exception("💩")
        stub_server.on_interaction.side_effect = stub_error

        with pytest.raises(Exception, match=".*") as exc_info:
            await adapter.process_request(http_scope, mock_receive, mock_send)

        assert exc_info.value is stub_error
        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": b"Internal Server Error",
                        "more_body": False,
                    }
                ),
            ]
        )
        mock_receive.assert_awaited_once_with()
        stub_server.on_interaction.assert_awaited_once_with(b"transive", b"trans", b"653245")

    @pytest.mark.asyncio()
    async def test_process_request_when_no_response_headers_or_body(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"Content-Type", b"application/json"),
            (b"random-header2", b"random value"),
            (b"x-signature-ed25519", b"6e796161"),
            (b"x-signature-timestamp", b"321123"),
            (b"random-header", b"random value"),
        ]
        mock_receive = mock.AsyncMock(
            side_effect=[{"body": b"cat", "more_body": True}, {"body": b"girls", "more_body": False}]
        )
        mock_send = mock.AsyncMock()
        stub_server.on_interaction.return_value.payload = None
        stub_server.on_interaction.return_value.headers = None

        await adapter.process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "type": "http.response.start",
                        "status": stub_server.on_interaction.return_value.status_code,
                        "headers": [],
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": b"",
                        "more_body": False,
                    }
                ),
            ]
        )
        mock_receive.assert_has_awaits([mock.call(), mock.call()])
        stub_server.on_interaction.assert_awaited_once_with(bytearray(b"catgirls"), b"nyaa", b"321123")
