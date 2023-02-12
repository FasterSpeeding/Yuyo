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

# pyright: reportPrivateUsage=none
# pyright: reportUnknownMemberType=none
# This leads to too many false-positives around mocks.

import asyncio
import concurrent.futures
import contextlib
import traceback
import types
import typing
import uuid
from collections import abc as collections
from unittest import mock

import asgiref.typing
import hikari
import hikari.files
import pytest

import yuyo


class _ChunkedReader(hikari.files.AsyncReader):
    __slots__ = ("_chunks",)

    def __init__(self, chunks: list[bytes], filename: str, /, *, mimetype: typing.Optional[str] = None) -> None:
        super().__init__(filename, mimetype)
        self._chunks = iter(chunks)

    async def __aiter__(self) -> collections.AsyncGenerator[typing.Any, bytes]:
        for value in self._chunks:
            yield value


class _NoOpAsyncReaderContextManagerImpl(hikari.files.AsyncReaderContextManager[hikari.files.ReaderImplT]):
    def __init__(self, reader: hikari.files.ReaderImplT, /) -> None:
        self._reader = reader

    async def __aenter__(self) -> hikari.files.ReaderImplT:
        return self._reader

    async def __aexit__(
        self,
        exc_type: typing.Optional[type[BaseException]],
        exc: typing.Optional[BaseException],
        exc_tb: typing.Optional[types.TracebackType],
    ) -> None:
        pass


class _ChunkedFile(hikari.files.Resource[_ChunkedReader]):
    __slots__ = ("_reader",)

    def __init__(self, chunks: list[bytes], filename: str, /, *, mimetype: typing.Optional[str] = None) -> None:
        self._reader = _ChunkedReader(chunks, filename, mimetype=mimetype)

    @property
    def filename(self) -> str:
        return self._reader.filename

    @property
    def url(self) -> str:
        raise NotImplementedError

    def stream(
        self, *, executor: typing.Optional[concurrent.futures.Executor] = None, head_only: bool = False
    ) -> hikari.files.AsyncReaderContextManager[_ChunkedReader]:
        return _NoOpAsyncReaderContextManagerImpl(self._reader)


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
    async def test_call_dunder_method_when_http(
        self, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ) -> None:
        mock_process_request = mock.AsyncMock()
        mock_receive = mock.Mock()
        mock_send = mock.Mock()

        class StubAdapter(yuyo.AsgiAdapter):
            _process_request = mock_process_request

        stub_adapter = StubAdapter(stub_server)

        await stub_adapter(http_scope, mock_receive, mock_send)

        mock_process_request.assert_awaited_once_with(http_scope, mock_receive, mock_send)

    @pytest.mark.asyncio()
    async def test_call_dunder_method_when_lifespan(self, stub_server: hikari.api.InteractionServer):
        mock_process_lifespan_event = mock.AsyncMock()
        mock_receive = mock.Mock()
        mock_send = mock.Mock()
        mock_scope = asgiref.typing.LifespanScope(
            type="lifespan", asgi=asgiref.typing.ASGIVersions(spec_version="ok", version="3.0")
        )

        class StubAdapter(yuyo.AsgiAdapter):
            _process_lifespan_event = mock_process_lifespan_event

        stub_adapter = StubAdapter(stub_server)

        await stub_adapter(mock_scope, mock_receive, mock_send)

        mock_process_lifespan_event.assert_awaited_once_with(mock_receive, mock_send)

    @pytest.mark.asyncio()
    async def test_call_dunder_method_when_webhook(self, adapter: yuyo.AsgiAdapter):
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

    def test_add_shutdown_callback(self, adapter: yuyo.AsgiAdapter):
        mock_callback = mock.AsyncMock()
        mock_other_callback = mock.AsyncMock()

        adapter.add_shutdown_callback(mock_callback)
        adapter.add_shutdown_callback(mock_other_callback)

        assert adapter.on_shutdown == [mock_callback, mock_other_callback]

    def test_remove_shutdown_callback(self, adapter: yuyo.AsgiAdapter):
        mock_callback = mock.AsyncMock()
        mock_other_callback = mock.AsyncMock()
        adapter.add_shutdown_callback(mock_callback)
        adapter.add_shutdown_callback(mock_other_callback)

        adapter.remove_shutdown_callback(mock_callback)

        assert adapter.on_shutdown == [mock_other_callback]

    def test_add_startup_callback(self, adapter: yuyo.AsgiAdapter):
        mock_callback = mock.AsyncMock()
        mock_other_callback = mock.AsyncMock()

        adapter.add_startup_callback(mock_callback)
        adapter.add_startup_callback(mock_other_callback)

        assert adapter.on_startup == [mock_callback, mock_other_callback]

    def test_remove_startup_callback(self, adapter: yuyo.AsgiAdapter):
        mock_callback = mock.AsyncMock()
        mock_other_callback = mock.AsyncMock()
        adapter.add_startup_callback(mock_callback)
        adapter.add_startup_callback(mock_other_callback)

        adapter.remove_startup_callback(mock_callback)

        assert adapter.on_startup == [mock_other_callback]

    @pytest.mark.asyncio()
    async def test__process_lifespan_event_on_startup(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.startup"})
        mock_send = mock.AsyncMock()

        await adapter._process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.startup.complete"})

    @pytest.mark.asyncio()
    async def test__process_lifespan_event_on_startup_with_callbacks(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.startup"})
        mock_send = mock.AsyncMock()
        mock_startup_callback = mock.AsyncMock()
        adapter.add_startup_callback(mock_startup_callback)

        await adapter._process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_startup_callback.assert_awaited_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.startup.complete"})

    @pytest.mark.asyncio()
    async def test__process_lifespan_event_on_startup_when_callback_fails(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.startup"})
        mock_send = mock.AsyncMock()
        mock_startup_callback = mock.AsyncMock(side_effect=Exception("test"))
        adapter.add_startup_callback(mock_startup_callback)

        with mock.patch.object(traceback, "format_exc") as format_exc:
            await adapter._process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_startup_callback.assert_awaited_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.startup.failed", "message": format_exc.return_value})
        format_exc.assert_called_once_with()

    @pytest.mark.asyncio()
    async def test__process_lifespan_event_on_shutdown(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.shutdown"})
        mock_send = mock.AsyncMock()

        await adapter._process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.shutdown.complete"})

    @pytest.mark.asyncio()
    async def test__process_lifespan_event_on_shutdown_with_callbacks(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.shutdown"})
        mock_send = mock.AsyncMock()
        mock_shutdown_callback = mock.AsyncMock()
        adapter.add_shutdown_callback(mock_shutdown_callback)

        await adapter._process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_shutdown_callback.assert_awaited_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.shutdown.complete"})

    @pytest.mark.asyncio()
    async def test__process_lifespan_event_on_shutdown_when_callback_fails(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.shutdown"})
        mock_send = mock.AsyncMock()
        mock_shutdown_callback = mock.AsyncMock()
        mock_startup_callback = mock.AsyncMock(side_effect=Exception("test"))
        adapter.add_shutdown_callback(mock_shutdown_callback)
        adapter.add_shutdown_callback(mock_startup_callback)

        with mock.patch.object(traceback, "format_exc") as format_exc:
            await adapter._process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_shutdown_callback.assert_awaited_once_with()
        mock_startup_callback.assert_awaited_once_with()
        mock_send.assert_awaited_once_with({"type": "lifespan.shutdown.failed", "message": format_exc.return_value})
        format_exc.assert_called_once_with()

    @pytest.mark.asyncio()
    async def test__process_lifespan_event_on_invalid_lifespan_type(self, adapter: yuyo.AsgiAdapter) -> None:
        mock_receive = mock.AsyncMock(return_value={"type": "lifespan.idk"})
        mock_send = mock.AsyncMock()

        with pytest.raises(RuntimeError, match="Unknown lifespan event lifespan.idk"):
            await adapter._process_lifespan_event(mock_receive, mock_send)

        mock_receive.assert_awaited_once_with()
        mock_send.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"Content-Type", b"application/json; charset=UTF-8"),
            (b"x-signature-timestamp", b"321123"),
            (b"random-header2", b"random value"),
            (b"x-signature-ed25519", b"6e796161"),
            (b"random-header", b"random value"),
        ]
        mock_receive = mock.AsyncMock(
            side_effect=[{"body": b"cat", "more_body": True}, {"body": b"girls", "more_body": False}]
        )
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.return_value.charset = "nyaa"
        stub_server.on_interaction.return_value.content_type = "jazz hands"
        stub_server.on_interaction.return_value.files = ()
        stub_server.on_interaction.return_value.headers = {
            "kill": "me baby",
            "I am the milk man": "my milk is delicious",
            "and the sea shall run white": "with his rage",
        }

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [
                            (b"kill", b"me baby"),
                            (b"I am the milk man", b"my milk is delicious"),
                            (b"and the sea shall run white", b"with his rage"),
                            (b"content-type", b"jazz hands; charset=nyaa"),
                        ],
                        "status": stub_server.on_interaction.return_value.status_code,
                        "trailers": False,
                        "type": "http.response.start",
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
    async def test__process_request_when_multipart_response(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"Content-Type", b"application/json"),
            (b"x-signature-timestamp", b"321123"),
            (b"random-header2", b"random value"),
            (b"x-signature-ed25519", b"6e796161"),
            (b"random-header", b"random value"),
        ]
        boundary_uuid = uuid.uuid4()
        mock_receive = mock.AsyncMock(
            side_effect=[{"body": b"cat", "more_body": True}, {"body": b"girls", "more_body": False}]
        )
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.return_value.charset = "nooooo"
        stub_server.on_interaction.return_value.content_type = "application/json"
        stub_server.on_interaction.return_value.files = [
            hikari.Bytes(b"beep beep\ni'm a sheep", "hi.txt", mimetype="text/plain"),
            hikari.Bytes(b"good\nbye\nmy\nMiku", "bye.exe", mimetype="fuckedup/me"),
        ]
        stub_server.on_interaction.return_value.headers = {
            "kill": "me baby",
            "I am the milk man": "my milk is delicious",
            "and the sea shall run white": "with his rage",
        }
        stub_server.on_interaction.return_value.payload = b'{"ok": "no", "byebye": "boomer"}'

        with mock.patch.object(uuid, "uuid4", return_value=boundary_uuid) as patched_uuid4:
            await adapter._process_request(http_scope, mock_receive, mock_send)

        patched_uuid4.assert_called_once_with()
        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [
                            (b"kill", b"me baby"),
                            (b"I am the milk man", b"my milk is delicious"),
                            (b"and the sea shall run white", b"with his rage"),
                            (b"content-type", b"multipart/form-data; boundary=" + boundary_uuid.hex.encode()),
                        ],
                        "status": stub_server.on_interaction.return_value.status_code,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": (
                            b'--%b\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-'  # noqa: MOD001
                            b'Type: application/json; charset=nooooo\r\nContent-Length: 32\r\n\r\n{"ok"'
                            b': "no", "byebye": "boomer"}' % boundary_uuid.hex.encode()
                        ),
                        "more_body": True,
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": (
                            b'\r\n--%b\r\nContent-Disposition: form-data; name="files[0]";'  # noqa: MOD001
                            b'filename="hi.txt"\r\nContent-Type: text/plain\r\n\r\nbeep beep\ni\'m a sheep'
                            % boundary_uuid.hex.encode()
                        ),
                        "more_body": True,
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": (
                            b'\r\n--%b\r\nContent-Disposition: form-data; name="files[1]";'  # noqa: MOD001
                            b'filename="bye.exe"\r\nContent-Type: fuckedup/me\r\n\r\ngood\nbye\nmy\nMiku'
                            % boundary_uuid.hex.encode()
                        ),
                        "more_body": True,
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": b"\r\n--%b--" % boundary_uuid.hex.encode(),  # noqa: MOD001
                        "more_body": False,
                    }
                ),
            ]
        )
        mock_receive.assert_has_awaits([mock.call(), mock.call()])
        stub_server.on_interaction.assert_awaited_once_with(bytearray(b"catgirls"), b"nyaa", b"321123")

    @pytest.mark.asyncio()
    async def test__process_request_when_chunked_file(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"Content-Type", b"application/json; charset=UTF-8"),
            (b"x-signature-timestamp", b"321123"),
            (b"random-header2", b"random value"),
            (b"x-signature-ed25519", b"6e796161"),
            (b"random-header", b"random value"),
        ]
        boundary_uuid = uuid.uuid4()
        mock_receive = mock.AsyncMock(
            side_effect=[{"body": b"cat", "more_body": True}, {"body": b"girls", "more_body": False}]
        )
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.return_value.charset = None
        stub_server.on_interaction.return_value.content_type = "application/json"
        stub_server.on_interaction.return_value.files = [
            _ChunkedFile(
                [b"chunk1\n\n\nhi bye", b"chunk\n22\n\n\nyeet", b"chunketh 3 ok"],
                "chunky.chunks",
                mimetype="split/me/up",
            ),
            hikari.Bytes(b"yeet meow\nnyaa", "yeet.txt", mimetype="text/plain"),
        ]
        stub_server.on_interaction.return_value.headers = {
            "kill": "me baby",
            "I am the milk man": "my milk is delicious",
            "and the sea shall run white": "with his rage",
        }
        stub_server.on_interaction.return_value.payload = b'{"ok": "no", "bye": "boom"}'

        with mock.patch.object(uuid, "uuid4", return_value=boundary_uuid) as patched_uuid4:
            await adapter._process_request(http_scope, mock_receive, mock_send)

        patched_uuid4.assert_called_once_with()
        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [
                            (b"kill", b"me baby"),
                            (b"I am the milk man", b"my milk is delicious"),
                            (b"and the sea shall run white", b"with his rage"),
                            (b"content-type", b"multipart/form-data; boundary=" + boundary_uuid.hex.encode()),
                        ],
                        "status": stub_server.on_interaction.return_value.status_code,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": (
                            b'--%b\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-'  # noqa: MOD001
                            b"Type: application/json\r\nContent-Length: 27\r\n\r\n{"
                            b'"ok": "no", "bye": "boom"}' % boundary_uuid.hex.encode()
                        ),
                        "more_body": True,
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": (
                            b'\r\n--%b\r\nContent-Disposition: form-data; name="files[0]";'  # noqa: MOD001
                            b'filename="chunky.chunks"\r\nContent-Type: split/me/up\r\n\r\nchunk1\n\n\nhi bye'
                            % boundary_uuid.hex.encode()
                        ),
                        "more_body": True,
                    }
                ),
                mock.call({"type": "http.response.body", "body": (b"chunk\n22\n\n\nyeet"), "more_body": True}),
                mock.call({"type": "http.response.body", "body": (b"chunketh 3 ok"), "more_body": True}),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": (
                            b'\r\n--%b\r\nContent-Disposition: form-data; name="files[1]";'  # noqa: MOD001
                            b'filename="yeet.txt"\r\nContent-Type: text/plain\r\n\r\nyeet meow\nnyaa'
                            % boundary_uuid.hex.encode()
                        ),
                        "more_body": True,
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": b"\r\n--%b--" % boundary_uuid.hex.encode(),  # noqa: MOD001
                        "more_body": False,
                    }
                ),
            ]
        )
        mock_receive.assert_has_awaits([mock.call(), mock.call()])
        stub_server.on_interaction.assert_awaited_once_with(bytearray(b"catgirls"), b"nyaa", b"321123")

    @pytest.mark.asyncio()
    async def test__process_request_when_empty_file(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"Content-Type", b"application/json; charset=UTF-8"),
            (b"x-signature-timestamp", b"321123"),
            (b"random-header2", b"random value"),
            (b"x-signature-ed25519", b"6e796161"),
            (b"random-header", b"random value"),
        ]
        boundary_uuid = uuid.uuid4()
        mock_receive = mock.AsyncMock(
            side_effect=[{"body": b"cat", "more_body": True}, {"body": b"girls", "more_body": False}]
        )
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.return_value.charset = "yeet"
        stub_server.on_interaction.return_value.content_type = "application/json"
        stub_server.on_interaction.return_value.files = [
            hikari.Bytes(b"", "empty.inside", mimetype="voided"),
            hikari.Bytes(b"good\nbye\nmy\nMiku", "bye.exe", mimetype="fuckedup/me"),
        ]
        stub_server.on_interaction.return_value.headers = {
            "kill": "me baby",
            "I am the milk man": "my milk is delicious",
            "and the sea shall run white": "with his rage",
        }
        stub_server.on_interaction.return_value.payload = b'{"ok": "yes", "yeet the": "boomer"}'

        with mock.patch.object(uuid, "uuid4", return_value=boundary_uuid) as patched_uuid4:
            await adapter._process_request(http_scope, mock_receive, mock_send)

        patched_uuid4.assert_called_once_with()
        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [
                            (b"kill", b"me baby"),
                            (b"I am the milk man", b"my milk is delicious"),
                            (b"and the sea shall run white", b"with his rage"),
                            (b"content-type", b"multipart/form-data; boundary=" + boundary_uuid.hex.encode()),
                        ],
                        "status": stub_server.on_interaction.return_value.status_code,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": (
                            b'--%b\r\nContent-Disposition: form-data; name="payload_json"\r\nContent-'  # noqa: MOD001
                            b'Type: application/json; charset=yeet\r\nContent-Length: 35\r\n\r\n{"ok": '
                            b'"yes", "yeet the": "boomer"}' % boundary_uuid.hex.encode()
                        ),
                        "more_body": True,
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": (
                            b'\r\n--%b\r\nContent-Disposition: form-data; name="files[0]";'  # noqa: MOD001
                            b'filename="empty.inside"\r\nContent-Type: voided\r\n\r\n' % boundary_uuid.hex.encode()
                        ),
                        "more_body": True,
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": (
                            b'\r\n--%b\r\nContent-Disposition: form-data; name="files[1]";'  # noqa: MOD001
                            b'filename="bye.exe"\r\nContent-Type: fuckedup/me\r\n\r\ngood\nbye\nmy\nMiku'
                            % boundary_uuid.hex.encode()
                        ),
                        "more_body": True,
                    }
                ),
                mock.call(
                    {
                        "type": "http.response.body",
                        "body": b"\r\n--%b--" % boundary_uuid.hex.encode(),  # noqa: MOD001
                        "more_body": False,
                    }
                ),
            ]
        )
        mock_receive.assert_has_awaits([mock.call(), mock.call()])
        stub_server.on_interaction.assert_awaited_once_with(bytearray(b"catgirls"), b"nyaa", b"321123")

    @pytest.mark.asyncio()
    async def test__process_request_when_not_post(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["method"] = "GET"
        http_scope["path"] = "/"
        mock_receive = mock.AsyncMock()
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 404,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"Not found", "more_body": False}),
            ]
        )
        mock_receive.assert_not_called()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request_when_not_base_route(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["method"] = "POST"
        http_scope["path"] = "/not-base-route"
        mock_receive = mock.AsyncMock()
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "trailers": False,
                        "status": 404,
                        "type": "http.response.start",
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"Not found", "more_body": False}),
            ]
        )
        mock_receive.assert_not_called()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request_when_no_body(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"random-header2", b"random value"),
            (b"x-signature-timestamp", b"653245"),
            (b"x-signature-ed25519", b"7472616e73"),
            (b"Content-Type", b"application/json"),
            (b"random-header", b"random value"),
        ]
        mock_receive = mock.AsyncMock(return_value={"body": b"", "more_body": False})
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 400,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"POST request must have a body", "more_body": False}),
            ]
        )
        mock_receive.assert_awaited_once_with()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request_when_no_body_and_receive_empty(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [
            (b"random-header2", b"random value"),
            (b"x-signature-timestamp", b"653245"),
            (b"x-signature-ed25519", b"7472616e73"),
            (b"Content-Type", b"application/json"),
            (b"random-header", b"random value"),
        ]
        mock_receive = mock.AsyncMock(return_value={})
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 400,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"POST request must have a body", "more_body": False}),
            ]
        )
        mock_receive.assert_awaited_once_with()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request_when_no_content_type(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = []
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 400,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call(
                    {"type": "http.response.body", "body": b"Content-Type must be application/json", "more_body": False}
                ),
            ]
        )
        mock_receive.assert_not_called()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request_when_not_json_content_type(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [(b"Content-Type", b"NOT JSON")]
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 400,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call(
                    {"type": "http.response.body", "body": b"Content-Type must be application/json", "more_body": False}
                ),
            ]
        )
        mock_receive.assert_not_called()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request_when_missing_timestamp_header(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [(b"Content-Type", b"application/json"), (b"x-signature-ed25519", b"676179")]
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 400,
                        "trailers": False,
                        "type": "http.response.start",
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
        mock_receive.assert_not_called()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request_when_missing_ed25519_header(
        self, adapter: yuyo.AsgiAdapter, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        http_scope["headers"] = [(b"Content-Type", b"application/json"), (b"x-signature-timestamp", b"87")]
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 400,
                        "trailers": False,
                        "type": "http.response.start",
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
        mock_receive.assert_not_called()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.parametrize("header_value", ["🇯🇵".encode(), b"trans"])
    @pytest.mark.asyncio()
    async def test__process_request_when_ed_25519_header_not_valid(
        self,
        adapter: yuyo.AsgiAdapter,
        stub_server: hikari.api.InteractionServer,
        http_scope: asgiref.typing.HTTPScope,
        header_value: bytes,
    ):
        http_scope["headers"] = [
            (b"Content-Type", b"application/json"),
            (b"x-signature-timestamp", b"87"),
            (b"x-signature-ed25519", header_value),
        ]
        mock_receive = mock.AsyncMock(return_value={"body": b"gay", "more_body": False})
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 400,
                        "trailers": False,
                        "type": "http.response.start",
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
        mock_receive.assert_not_called()
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request_when_body_too_big(
        self, stub_server: hikari.api.InteractionServer, http_scope: asgiref.typing.HTTPScope
    ):
        adapter = yuyo.AsgiAdapter(stub_server, max_body_size=64)

        http_scope["headers"] = [
            (b"Content-Type", b"application/json"),
            (b"x-signature-timestamp", b"b" * 32),
            (b"x-signature-ed25519", b"a" * 64),
        ]
        mock_receive = mock.AsyncMock(
            side_effect=[
                {"body": b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "more_body": True},
                {"body": b"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "more_body": True},
            ]
        )
        mock_send = mock.AsyncMock()
        assert isinstance(stub_server.on_interaction, mock.Mock)

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 413,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"Content Too Large", "more_body": False}),
            ]
        )
        mock_receive.assert_has_awaits([mock.call(), mock.call()])
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.assert_not_called()

    @pytest.mark.asyncio()
    async def test__process_request_when_on_interaction_raises(
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
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.side_effect = stub_error

        with pytest.raises(Exception, match=".*") as exc_info:
            await adapter._process_request(http_scope, mock_receive, mock_send)

        assert exc_info.value is stub_error
        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
                        "status": 500,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"Internal Server Error", "more_body": False}),
            ]
        )
        mock_receive.assert_awaited_once_with()
        stub_server.on_interaction.assert_awaited_once_with(b"transive", b"trans", b"653245")

    @pytest.mark.asyncio()
    async def test__process_request_when_no_response_headers_or_body(
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
        assert isinstance(stub_server.on_interaction, mock.Mock)
        stub_server.on_interaction.return_value.content_type = None
        stub_server.on_interaction.return_value.files = ()
        stub_server.on_interaction.return_value.payload = None
        stub_server.on_interaction.return_value.headers = None

        await adapter._process_request(http_scope, mock_receive, mock_send)

        mock_send.assert_has_awaits(
            [
                mock.call(
                    {
                        "headers": [],
                        "status": stub_server.on_interaction.return_value.status_code,
                        "trailers": False,
                        "type": "http.response.start",
                    }
                ),
                mock.call({"type": "http.response.body", "body": b"", "more_body": False}),
            ]
        )
        mock_receive.assert_has_awaits([mock.call(), mock.call()])
        stub_server.on_interaction.assert_awaited_once_with(bytearray(b"catgirls"), b"nyaa", b"321123")


class TestAsgiBot:
    def test___init___when_asgi_managed(self) -> None:
        with mock.patch.object(hikari.impl, "EntityFactoryImpl") as mock_entity_factory_impl:
            bot = yuyo.AsgiBot("token", "Bot")

            assert bot.entity_factory is mock_entity_factory_impl.return_value
            mock_entity_factory_impl.assert_called_once_with(bot)

            assert bot._start in bot._adapter.on_startup
            assert bot._close in bot._adapter.on_shutdown

    def test___init___when_not_asgi_managed(self) -> None:
        with mock.patch.object(hikari.impl, "EntityFactoryImpl") as mock_entity_factory_impl:
            bot = yuyo.AsgiBot("token", "Bot", asgi_managed=False)

            assert bot.entity_factory is mock_entity_factory_impl.return_value
            mock_entity_factory_impl.assert_called_once_with(bot)

            assert bot._start not in bot._adapter.on_startup
            assert bot._close not in bot._adapter.on_shutdown

    def test_entity_factory_property(self):
        with mock.patch.object(hikari.impl, "EntityFactoryImpl") as mock_entity_factory_impl:
            bot = yuyo.AsgiBot("token", "Bot")

            assert bot.entity_factory is mock_entity_factory_impl.return_value
            mock_entity_factory_impl.assert_called_once_with(bot)

    def test_executor_property(self):
        mock_executor = mock.Mock()

        with mock.patch.object(hikari.impl, "RESTClientImpl") as mock_rest_client_impl:
            bot = yuyo.AsgiBot("token", "Bot", executor=mock_executor)

            mock_rest_client_impl.assert_called_once_with(  # noqa: S106
                cache=None,
                entity_factory=bot.entity_factory,
                executor=mock_executor,
                http_settings=bot.http_settings,
                max_rate_limit=300.0,
                proxy_settings=bot.proxy_settings,
                rest_url=None,
                token="token",
                token_type="Bot",
                max_retries=3,
            )

        assert bot.executor is mock_executor

    def test_executor_property_when_no_executor(self):
        bot = yuyo.AsgiBot("token", "Bot")

        assert bot.executor is None

    def test_http_settings_property(self):
        with mock.patch.object(hikari.impl, "HTTPSettings") as mock_http_settings:
            bot = yuyo.AsgiBot("token", "Bot")

            assert bot.http_settings is mock_http_settings.return_value
            mock_http_settings.assert_called_once_with()

    def test_http_settings_property_when_passed_through(self):
        mock_settings = mock.Mock()

        with mock.patch.object(hikari.impl, "RESTClientImpl") as mock_rest_client_impl:
            bot = yuyo.AsgiBot("token", "Bot", http_settings=mock_settings)

            mock_rest_client_impl.assert_called_once_with(  # noqa: S106
                cache=None,
                entity_factory=bot.entity_factory,
                executor=None,
                http_settings=mock_settings,
                max_rate_limit=300.0,
                proxy_settings=bot.proxy_settings,
                rest_url=None,
                token="token",
                token_type="Bot",
                max_retries=3,
            )

        assert bot.http_settings is mock_settings

    def test_interaction_server_property(self):
        with mock.patch.object(hikari.impl, "InteractionServer") as mock_interaction_server:
            bot = yuyo.AsgiBot("token", "Bot", public_key=b"osososo")

            assert bot.interaction_server is mock_interaction_server.return_value
            mock_interaction_server.assert_called_once_with(
                entity_factory=bot.entity_factory, rest_client=bot.rest, public_key=b"osososo"
            )

    def test_proxy_settings_property(self):
        with mock.patch.object(hikari.impl, "ProxySettings") as mock_proxy_settings:
            bot = yuyo.AsgiBot("token", "Bot")

            assert bot.proxy_settings is mock_proxy_settings.return_value
            mock_proxy_settings.assert_called_once_with()

    def test_proxy_settings_property_when_passed_through(self):
        mock_settings = mock.Mock()

        with mock.patch.object(hikari.impl, "RESTClientImpl") as mock_rest_client_impl:
            bot = yuyo.AsgiBot("token", "Bot", proxy_settings=mock_settings)

            mock_rest_client_impl.assert_called_once_with(  # noqa: S106
                cache=None,
                entity_factory=bot.entity_factory,
                executor=None,
                http_settings=bot.http_settings,
                max_rate_limit=300.0,
                proxy_settings=mock_settings,
                rest_url=None,
                token="token",
                token_type="Bot",
                max_retries=3,
            )

        assert bot.proxy_settings is mock_settings

    def test_rest_property(self):
        with mock.patch.object(hikari.impl, "RESTClientImpl") as mock_rest_client_impl:
            bot = yuyo.AsgiBot("token", "Bot")

            mock_rest_client_impl.assert_called_once_with(  # noqa: S106
                cache=None,
                entity_factory=bot.entity_factory,
                executor=None,
                http_settings=bot.http_settings,
                max_rate_limit=300.0,
                proxy_settings=bot.proxy_settings,
                rest_url=None,
                token="token",
                token_type="Bot",
                max_retries=3,
            )
            assert bot.rest is mock_rest_client_impl.return_value

    @pytest.mark.asyncio()
    async def test_call_dunder_method(self):
        mock_send = mock.AsyncMock()
        mock_recv = mock.AsyncMock()
        mock_scope = mock.Mock()
        # I'd rather just use spec here but that doesn't work cause of
        # https://github.com/python/cpython/issues/71902
        mock_adapter = mock.AsyncMock(add_shutdown_callback=mock.Mock(), add_startup_callback=mock.Mock())

        with mock.patch.object(yuyo.asgi, "AsgiAdapter", return_value=mock_adapter):
            bot = yuyo.AsgiBot("token", "Bot")

        await bot(mock_scope, mock_recv, mock_send)

        mock_adapter.assert_awaited_once_with(mock_scope, mock_recv, mock_send)

    def test_run(self):
        stack = contextlib.ExitStack()
        mock_get_running_loop = stack.enter_context(mock.patch.object(asyncio, "get_running_loop"))
        mock_make_event_loop = stack.enter_context(mock.patch.object(asyncio, "new_event_loop"))
        mock_set_event_loop = stack.enter_context(mock.patch.object(asyncio, "set_event_loop"))
        mock_loop = mock_get_running_loop.return_value
        mock_start = mock.Mock()
        mock_join = mock.Mock()

        class StubBot(yuyo.AsgiBot):
            start = mock_start
            join = mock_join

        bot = StubBot("token", "Bot", asgi_managed=False)

        with stack:
            bot.run()

        mock_get_running_loop.assert_called_once_with()
        mock_make_event_loop.assert_not_called()
        mock_set_event_loop.assert_not_called()
        mock_start.assert_called_once_with()
        mock_join.assert_called_once_with()
        mock_loop.run_until_complete.assert_has_calls(
            [mock.call(mock_start.return_value), mock.call(mock_join.return_value)]
        )

    def test_run_makes_new_event_loop(self):
        stack = contextlib.ExitStack()
        mock_get_running_loop = stack.enter_context(
            mock.patch.object(asyncio, "get_running_loop", side_effect=RuntimeError)
        )
        mock_make_event_loop = stack.enter_context(mock.patch.object(asyncio, "new_event_loop"))
        mock_set_event_loop = stack.enter_context(mock.patch.object(asyncio, "set_event_loop"))
        mock_loop = mock_make_event_loop.return_value
        mock_start = mock.Mock()
        mock_join = mock.Mock()

        class StubBot(yuyo.AsgiBot):
            start = mock_start
            join = mock_join

        bot = StubBot("token", "Bot", asgi_managed=False)

        with stack:
            bot.run()

        mock_get_running_loop.assert_called_once_with()
        mock_make_event_loop.assert_called_once_with()
        mock_set_event_loop.assert_called_once_with(mock_loop)
        mock_start.assert_called_once_with()
        mock_join.assert_called_once_with()
        mock_loop.run_until_complete.assert_has_calls(
            [mock.call(mock_start.return_value), mock.call(mock_join.return_value)]
        )

    @pytest.mark.asyncio()
    async def test_run_when_already_alive(self):
        mock_join = mock.Mock()

        class StubBot(yuyo.AsgiBot):
            join = mock_join

        with mock.patch.object(hikari.impl, "RESTClientImpl"):
            bot = StubBot("token", "Bot", asgi_managed=False)

        await bot.start()

        with pytest.raises(RuntimeError, match="The client is already running"):
            bot.run()

        mock_join.assert_not_called()

    def test_run_when_asgi_managed(self):
        mock_start = mock.Mock()
        mock_join = mock.Mock()

        class StubBot(yuyo.AsgiBot):
            start = mock_start
            join = mock_join

        bot = StubBot("token", "Bot")

        with pytest.raises(RuntimeError, match="The client is being managed by ASGI lifespan events"):
            bot.run()

        mock_start.assert_not_called()
        mock_join.assert_not_called()

    @pytest.mark.asyncio()
    async def test_start(self):
        stack = contextlib.ExitStack()
        mock_rest_client_impl = stack.enter_context(mock.patch.object(hikari.impl, "RESTClientImpl"))
        mock_event = stack.enter_context(mock.patch.object(asyncio, "Event"))
        with stack:
            bot = yuyo.AsgiBot("token", "Bot", asgi_managed=False)

            await bot.start()

            assert bot.is_alive is True
            assert bot._join_event is mock_event.return_value

        mock_rest_client_impl.return_value.start.assert_called_once_with()
        mock_event.assert_called_once_with()

    @pytest.mark.asyncio()
    async def test_start_when_asgi_managed(self):
        with mock.patch.object(hikari.impl, "RESTClientImpl"):
            bot = yuyo.AsgiBot("token", "Bot")

        with pytest.raises(RuntimeError, match="The client is being managed by ASGI lifespan events"):
            await bot.start()

    @pytest.mark.asyncio()
    async def test_start_when_already_alive(self):
        with mock.patch.object(hikari.impl, "RESTClientImpl"):
            bot = yuyo.AsgiBot("token", "Bot", asgi_managed=False)

        await bot.start()

        with pytest.raises(RuntimeError, match="The client is already running"):
            await bot.start()

    @pytest.mark.asyncio()
    async def test_close_when_asgi_managed(self):
        bot = yuyo.AsgiBot("token", "Bot")

        with pytest.raises(RuntimeError, match="The client is being managed by ASGI lifespan events"):
            await bot.close()

    @pytest.mark.asyncio()
    async def test_close(self):
        stack = contextlib.ExitStack()
        mock_rest_client_impl = stack.enter_context(mock.patch.object(hikari.impl, "RESTClientImpl"))
        mock_rest_client_impl.return_value.close = mock.AsyncMock()
        mock_event = stack.enter_context(mock.patch.object(asyncio, "Event"))
        with stack:
            bot = yuyo.AsgiBot("token", "Bot", asgi_managed=False)

            await bot.start()

            mock_rest_client_impl.return_value.close.assert_not_called()
            mock_event.return_value.set.assert_not_called()

            await bot.close()

            assert bot.is_alive is False
            assert bot._join_event is None

        mock_rest_client_impl.return_value.close.assert_awaited_once_with()
        mock_event.return_value.set.assert_called_once_with()

    @pytest.mark.asyncio()
    async def test_close_when_not_alive(self):
        bot = yuyo.AsgiBot("token", "Bot", asgi_managed=False)

        with pytest.raises(RuntimeError, match="The client is not running"):
            await bot.close()

    @pytest.mark.asyncio()
    async def test_join(self):
        with mock.patch.object(hikari.impl, "RESTClientImpl"):
            bot = yuyo.AsgiBot("token", "Bot", asgi_managed=False)

        with mock.patch.object(asyncio, "Event", return_value=mock.AsyncMock()) as join_event:
            await bot.start()

        join_event.assert_called_once_with()
        join_event.return_value.wait.assert_not_called()

        await bot.join()
        join_event.return_value.wait.assert_awaited_once_with()

    @pytest.mark.asyncio()
    async def test_join_when_not_alive(self):
        bot = yuyo.AsgiBot("token", "Bot")

        with pytest.raises(RuntimeError, match="The client is not running"):
            await bot.join()

    @pytest.mark.asyncio()
    async def test_add_shutdown_callback(self):
        mock_callback = mock.AsyncMock()
        bot = yuyo.AsgiBot("yeet", "Bot")

        bot.add_shutdown_callback(mock_callback)

        assert bot.on_shutdown == [mock_callback]
        assert len(bot._adapter.on_shutdown) == 2
        mock_callback.assert_not_called()
        await bot._adapter.on_shutdown[1]()
        mock_callback.assert_awaited_once_with(bot)

    @pytest.mark.asyncio()
    async def test_add_shutdown_callback_when_callback_already_registered(self):
        mock_callback = mock.AsyncMock()
        bot = yuyo.AsgiBot("yeet", "Bot")

        bot.add_shutdown_callback(mock_callback)
        bot.add_shutdown_callback(mock_callback)

        assert bot.on_shutdown == [mock_callback]
        assert len(bot._adapter.on_shutdown) == 2

    @pytest.mark.asyncio()
    async def test_remove_shutdown_callback(self):
        mock_callback = mock.AsyncMock()
        bot = yuyo.AsgiBot("yeet", "Bot")
        bot.add_shutdown_callback(mock_callback)
        assert bot.on_shutdown == [mock_callback]
        assert len(bot._adapter.on_shutdown) == 2

        bot.remove_shutdown_callback(mock_callback)

        assert bot.on_shutdown == []
        assert len(bot._adapter.on_shutdown) == 1

        bot.add_shutdown_callback(mock_callback)

        assert bot.on_shutdown == [mock_callback]
        assert len(bot._adapter.on_shutdown) == 2

    @pytest.mark.asyncio()
    async def test_remove_shutdown_callback_when_callback_not_registered(self):
        mock_callback = mock.AsyncMock()
        bot = yuyo.AsgiBot("yeet", "Bot")

        bot.remove_shutdown_callback(mock_callback)

        assert bot.on_shutdown == []
        assert len(bot._adapter.on_shutdown) == 1

    @pytest.mark.asyncio()
    async def test_add_startup_callback(self):
        mock_callback = mock.AsyncMock()
        bot = yuyo.AsgiBot("yeet", "Bot")

        bot.add_startup_callback(mock_callback)

        assert bot.on_startup == [mock_callback]
        assert len(bot._adapter.on_startup) == 2
        mock_callback.assert_not_called()
        await bot._adapter.on_startup[1]()
        mock_callback.assert_awaited_once_with(bot)

    @pytest.mark.asyncio()
    async def test_add_startup_callback_when_callback_already_registered(self):
        mock_callback = mock.AsyncMock()
        bot = yuyo.AsgiBot("yeet", "Bot")

        bot.add_startup_callback(mock_callback)
        bot.add_startup_callback(mock_callback)

        assert bot.on_startup == [mock_callback]
        assert len(bot._adapter.on_startup) == 2

    @pytest.mark.asyncio()
    async def test_remove_startup_callback(self):
        mock_callback = mock.AsyncMock()
        bot = yuyo.AsgiBot("yeet", "Bot")
        bot.add_startup_callback(mock_callback)
        assert bot.on_startup == [mock_callback]
        assert len(bot._adapter.on_startup) == 2

        bot.remove_startup_callback(mock_callback)

        assert bot.on_startup == []
        assert len(bot._adapter.on_startup) == 1

        bot.add_startup_callback(mock_callback)

        assert bot.on_startup == [mock_callback]
        assert len(bot._adapter.on_startup) == 2

    @pytest.mark.asyncio()
    async def test_remove_startup_callback_when_callback_not_registered(self):
        mock_callback = mock.AsyncMock()
        bot = yuyo.AsgiBot("yeet", "Bot")

        bot.remove_startup_callback(mock_callback)

        assert bot.on_startup == []
        assert len(bot._adapter.on_startup) == 1
