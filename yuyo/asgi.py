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
"""ASGI/3 adapter for Hikari's interaction server."""
from __future__ import annotations

__all__: typing.Sequence[str] = ["AsgiAdapter"]

import asyncio
import logging
import traceback
import typing

import asgiref.typing as asgiref
import hikari

_AsgiAdapterT = typing.TypeVar("_AsgiAdapterT", bound="AsgiAdapter")


_LOGGER = logging.getLogger("hikari.yuyo.asgi")
_CONTENT_TYPE_KEY: typing.Final[bytes] = b"content-type"
_JSON_CONTENT_TYPE: typing.Final[bytes] = b"application/json"
_BAD_REQUEST_STATUS: typing.Final[int] = 400
_X_SIGNATURE_ED25519_HEADER: typing.Final[bytes] = b"x-signature-ed25519"
_X_SIGNATURE_TIMESTAMP_HEADER: typing.Final[bytes] = b"x-signature-timestamp"
_TEXT_CONTENT_TYPE: typing.Final[bytes] = b"text/plain; charset=UTF-8"


async def _error_response(send: asgiref.ASGISendCallable, body: bytes) -> None:
    await send(
        asgiref.HTTPResponseStartEvent(
            type="http.response.start",
            status=_BAD_REQUEST_STATUS,
            headers=[
                (b"content-type", _TEXT_CONTENT_TYPE),
            ],
        )
    )
    await send(asgiref.HTTPResponseBodyEvent(type="http.response.body", body=body, more_body=False))


class AsgiAdapter:
    __slots__ = ("_on_shutdown", "_on_startup", "_server")

    def __init__(self, server: hikari.api.InteractionServer, /) -> None:
        self._on_shutdown: typing.List[typing.Callable[[], typing.Awaitable[None]]] = []
        self._on_startup: typing.List[typing.Callable[[], typing.Awaitable[None]]] = []
        self._server = server

    @property
    def server(self) -> hikari.api.InteractionServer:
        return self._server

    async def __call__(
        self, scope: asgiref.Scope, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable
    ) -> None:
        if scope["type"] == "http":
            await self.process_request(scope, receive, send)

        elif scope["type"] == "lifespan":
            await self.process_lifespan_event(receive, send)

        else:
            raise ValueError("Websocket operations are not supported")

    def add_shutdown_callback(
        self: _AsgiAdapterT, callback: typing.Callable[[], typing.Awaitable[None]], /
    ) -> _AsgiAdapterT:
        self._on_shutdown.append(callback)
        return self

    def add_startup_callback(
        self: _AsgiAdapterT, callback: typing.Callable[[], typing.Awaitable[None]], /
    ) -> _AsgiAdapterT:
        self._on_startup.append(callback)
        return self

    async def process_lifespan_event(
        self, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable
    ) -> None:
        message = await receive()
        message_type = message["type"]

        if message_type == "lifespan.startup":
            try:
                await asyncio.gather(*(callback() for callback in self._on_startup))

            except BaseException:
                await send({"type": "lifespan.startup.failed", "message": traceback.format_exc()})

            else:
                await send({"type": "lifespan.startup.complete"})

        elif message_type == "lifespan.shutdown":
            try:
                await asyncio.gather(*(callback() for callback in self._on_shutdown))

            except BaseException:
                await send({"type": "lifespan.shutdown.failed", "message": traceback.format_exc()})

            else:
                await send({"type": "lifespan.shutdown.complete"})

        else:
            raise ValueError(f"Unknown lifespan event {message_type}")

    async def process_request(
        self, scope: asgiref.HTTPScope, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable, /
    ) -> None:
        more_body = True
        body = bytearray()
        while more_body:
            received = await receive()

            if next_body := received.get("body"):
                body.extend(next_body)

            more_body = received.get("more_body", False)

        if not body:
            await _error_response(send, b"POST request must have a body")
            return

        content_type: typing.Optional[bytes] = None
        signature: typing.Optional[bytes] = None
        timestamp: typing.Optional[bytes] = None
        for name, value in scope["headers"]:
            # As per-spec these should be matched case-insensitively.
            name = name.lower()
            if name == _X_SIGNATURE_ED25519_HEADER:
                try:
                    signature = bytes.fromhex(value.decode("ascii"))

                # Yes UnicodeDecodeError means failed ascii decode.
                except (ValueError, UnicodeDecodeError):
                    await _error_response(send, b"Invalid ED25519 signature header found")
                    return

                if timestamp and content_type:
                    break

            elif name == _X_SIGNATURE_TIMESTAMP_HEADER:
                timestamp = value
                if signature and content_type:
                    break

            elif name == _CONTENT_TYPE_KEY:
                content_type = value
                if signature and timestamp:
                    break

        if not content_type or content_type.lower().split(b";", 1)[0] != _JSON_CONTENT_TYPE:
            await _error_response(send, b"Content-Type must be application/json")
            return

        if not signature or not timestamp:
            await _error_response(send, b"Missing or invalid required request signature header(s)")
            return

        response = await self.server.on_interaction(body, signature, timestamp)
        headers: typing.List[typing.Tuple[bytes, bytes]] = []
        if response.headers:
            headers.extend((key.encode(), value.encode()) for key, value in response.headers.items())

        response_dict = asgiref.HTTPResponseStartEvent(
            type="http.response.start", status=response.status_code, headers=headers
        )
        await send(response_dict)
        await send(
            asgiref.HTTPResponseBodyEvent(type="http.response.body", body=response.payload or b"", more_body=False)
        )
