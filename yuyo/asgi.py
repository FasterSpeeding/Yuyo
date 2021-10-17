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

import logging
import typing

import asgiref.typing as asgiref

if typing.TYPE_CHECKING:
    from hikari.api import interaction_server


_LOGGER = logging.getLogger("hikari.yuyo.asgi")
_CONTENT_TYPE_KEY: typing.Final[bytes] = b"Content-Type"
_JSON_CONTENT_TYPE: typing.Final[bytes] = b"application/json"
_BAD_REQUEST_STATUS: typing.Final[int] = 400
_X_SIGNATURE_ED25519_HEADER: typing.Final[bytes] = b"X-Signature-Ed25519".lower()
_X_SIGNATURE_TIMESTAMP_HEADER: typing.Final[bytes] = b"X-Signature-Timestamp".lower()
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
    __slots__ = ("server",)

    def __init__(self, server: interaction_server.InteractionServer, /) -> None:
        self.server = server

    async def __call__(
        self, scope: asgiref.HTTPScope, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable
    ) -> None:
        await self.receive(scope, receive, send)

    async def receive(
        self, scope: asgiref.HTTPScope, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable
    ) -> None:
        assert scope["type"] == "http"
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
                    break

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
        headers: typing.Iterable[typing.Tuple[bytes, bytes]]
        if response.headers:
            headers = ((key.encode(), value.encode()) for key, value in response.headers.items())

        else:
            headers = ()

        response_dict = asgiref.HTTPResponseStartEvent(
            type="http.response.start", status=response.status_code, headers=headers
        )

        await send(response_dict)
        await send(
            asgiref.HTTPResponseBodyEvent(type="http.response.body", body=response.payload or b"", more_body=False)
        )
