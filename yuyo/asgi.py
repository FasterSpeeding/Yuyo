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
"""ASGI/3 adapter for Hikari's interaction server."""
from __future__ import annotations

__all__: list[str] = ["AsgiAdapter", "AsgiBot"]

import asyncio
import traceback
import typing
import urllib.parse
import uuid

import hikari

from . import _internal

if typing.TYPE_CHECKING:
    import concurrent.futures
    from collections import abc as collections

    import asgiref.typing as asgiref
    from hikari.api import config as hikari_config
    from typing_extensions import Self


_CONTENT_TYPE_KEY: typing.Final[bytes] = b"content-type"
_RAW_JSON_CONTENT_TYPE: typing.Final[bytes] = b"application/json"
_JSON_CONTENT_TYPE: typing.Final[bytes] = _RAW_JSON_CONTENT_TYPE + b"; charset=UTF-8"
_OCTET_STREAM_CONTENT_TYPE: typing.Final[bytes] = b"application/octet-stream"
_BAD_REQUEST_STATUS: typing.Final[int] = 400
_X_SIGNATURE_ED25519_HEADER: typing.Final[bytes] = b"x-signature-ed25519"
_X_SIGNATURE_TIMESTAMP_HEADER: typing.Final[bytes] = b"x-signature-timestamp"
_MULTIPART_CONTENT_TYPE: typing.Final[bytes] = b"multipart/form-data; boundary=%b"
_TEXT_CONTENT_TYPE: typing.Final[bytes] = b"text/plain; charset=UTF-8"


async def _error_response(
    send: asgiref.ASGISendCallable, body: bytes, /, *, status_code: int = _BAD_REQUEST_STATUS
) -> None:
    await send(
        {
            "headers": [(_CONTENT_TYPE_KEY, _TEXT_CONTENT_TYPE)],
            "status": status_code,
            "trailers": False,
            "type": "http.response.start",
        }
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


class AsgiAdapter:
    """Asgi/3 adapter for Hikari's interaction server interface.

    For this to work, hikari has to be installed with the optional "server"
    feature (e.g `python -m pip install hikari[server]`).
    """

    __slots__ = ("_executor", "_max_body_size", "_on_shutdown", "_on_startup", "_server")

    def __init__(
        self,
        server: hikari.api.InteractionServer,
        /,
        *,
        executor: typing.Optional[concurrent.futures.Executor] = None,
        max_body_size: int = 1024**2,
    ) -> None:
        """Initialise the adapter.

        Parameters
        ----------
        server
            The interaction server to use.
        executor
            If non-[None][], then this executor is used instead of the
            [concurrent.futures.ThreadPoolExecutor][] attached to the
            [asyncio.AbstractEventLoop][] that the bot will run on. This
            executor is used primarily for file-IO.

            While mainly supporting the [concurrent.futures.ThreadPoolExecutor][]
            implementation in the standard lib, Hikari's file handling systems
            should also work with [concurrent.futures.ProcessPoolExecutor][], which
            relies on all objects used in IPC to be `pickle`able. Many third-party
            libraries will not support this fully though, so your mileage may vary
            on using ProcessPoolExecutor implementations with this parameter.
        max_body_size
            The maximum body size this should allow received request bodies to be
            in bytes before failing the request with a 413 - Content Too Large.
        """
        self._executor = executor
        self._max_body_size = max_body_size
        self._on_shutdown: list[collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, None]]] = []
        self._on_startup: list[collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, None]]] = []
        self._server = server

    @property
    def on_shutdown(
        self,
    ) -> collections.Sequence[collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, None]]]:
        return self._on_shutdown

    @property
    def on_startup(
        self,
    ) -> collections.Sequence[collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, None]]]:
        return self._on_startup

    @property
    def server(self) -> hikari.api.InteractionServer:
        """The interaction server this adapter is bound to."""
        return self._server

    async def __call__(
        self, scope: asgiref.Scope, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable, /
    ) -> None:
        """Call the adapter.

        !!! note
            This method is called by the ASGI server.

        Parameters
        ----------
        scope
            The scope of the request.
        receive
            The receive function to use.
        send
            The send function to use.

        Raises
        ------
        NotImplementedError
            If this is called with a websocket scope.
        RuntimeError
            If an invalid scope event is passed.
        """
        if scope["type"] == "http":
            await self._process_request(scope, receive, send)

        elif scope["type"] == "lifespan":
            await self._process_lifespan_event(receive, send)

        else:
            raise NotImplementedError("Websocket operations are not supported")

    def add_shutdown_callback(
        self, callback: collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, None]], /
    ) -> Self:
        """Add a callback to be called when the ASGI server shuts down.

        !!! warning
            These callbacks will block the ASGI server from shutting down until
            they complete and any raised errors will lead to a failed shutdown.

        Parameters
        ----------
        callback
            The shutdown callback to add.

        Returns
        -------
        Self
            The adapter to enable chained calls.
        """
        self._on_shutdown.append(callback)
        return self

    def remove_shutdown_callback(
        self, callback: collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, None]], /
    ) -> Self:
        """Remove a shutdown callback.

        Parameters
        ----------
        callback
            The shutdown callback to remove.

        Returns
        -------
        Self
            The adapter to enable chained calls.

        Raises
        ------
        ValueError
            If the callback was not registered.
        """
        self._on_shutdown.remove(callback)
        return self

    def add_startup_callback(
        self, callback: collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, None]], /
    ) -> Self:
        """Add a callback to be called when the ASGI server starts up.

        !!! warning
            These callbacks will block the ASGI server from starting until
            they complete and any raised errors will lead to a failed startup.

        Parameters
        ----------
        callback
            The startup callback to add.

        Returns
        -------
        Self
            The adapter to enable chained calls.
        """
        self._on_startup.append(callback)
        return self

    def remove_startup_callback(
        self, callback: collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, None]], /
    ) -> Self:
        """Remove a startup callback.

        Parameters
        ----------
        callback
            The startup callback to remove.

        Returns
        -------
        Self
            The adapter to enable chained calls.

        Raises
        ------
        ValueError
            If the callback was not registered.
        """
        self._on_startup.remove(callback)
        return self

    async def _process_lifespan_event(
        self, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable, /
    ) -> None:
        """Process a lifespan ASGI event.

        !!! note
            This function is used internally by the adapter.

        Parameters
        ----------
        receive
            The receive function to use.
        send
            The send function to use.

        Raises
        ------
        RuntimeError
            If an invalid lifespan event is passed.
        """
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
            raise RuntimeError(f"Unknown lifespan event {message_type}")

    async def _process_request(
        self, scope: asgiref.HTTPScope, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable, /
    ) -> None:
        """Process an HTTP request.

        !!! note
            This function is used internally by the adapter.

        Parameters
        ----------
        scope
            The scope of the request.
        receive
            The receive function to use.
        send
            The send function to use.
        """
        if scope["method"] != "POST" or scope["path"] != "/":
            await _error_response(send, b"Not found", status_code=404)
            return

        try:
            content_type, signature, timestamp = _find_headers(scope)

        # Yes UnicodeDecodeError means failed ascii decode.
        except (ValueError, UnicodeDecodeError):
            await _error_response(send, b"Invalid ED25519 signature header found")
            return

        if not content_type or content_type.lower().split(b";", 1)[0] != _RAW_JSON_CONTENT_TYPE:
            await _error_response(send, b"Content-Type must be application/json")
            return

        if not signature or not timestamp:
            await _error_response(send, b"Missing required request signature header(s)")
            return

        more_body = True
        body = bytearray()
        while more_body:
            received = await receive()

            if next_body := received.get("body"):
                body.extend(next_body)

            if len(body) > self._max_body_size:
                await _error_response(send, b"Content Too Large", status_code=413)
                return

            more_body = received.get("more_body", False)

        if not body:
            await _error_response(send, b"POST request must have a body")
            return

        try:
            response = await self.server.on_interaction(body, signature, timestamp)
        except Exception:
            await _error_response(send, b"Internal Server Error", status_code=500)
            raise

        headers: list[tuple[bytes, bytes]] = []
        if response.headers:
            headers.extend((key.encode(), value.encode()) for key, value in response.headers.items())

        boundary = None
        if response.files:
            boundary = uuid.uuid4().hex.encode()
            headers.append((_CONTENT_TYPE_KEY, _MULTIPART_CONTENT_TYPE % boundary))  # noqa: S001

        elif content_type := _content_type(response):
            headers.append((_CONTENT_TYPE_KEY, content_type))

        await send(
            {"headers": headers, "status": response.status_code, "trailers": False, "type": "http.response.start"}
        )

        if boundary:
            await self._send_multipart(send, response, boundary)

        else:
            await send({"type": "http.response.body", "body": response.payload or b"", "more_body": False})

    async def _send_multipart(
        self, send: asgiref.ASGISendCallable, response: hikari.api.Response, boundary: bytes, /
    ) -> None:
        if response.payload:
            content_type = _content_type(response) or _JSON_CONTENT_TYPE
            body = (
                b'--%b\r\nContent-Disposition: form-data; name="payload_json"'  # noqa: MOD001
                b"\r\nContent-Type: %b\r\nContent-Length: %i\r\n\r\n%b"  # noqa: MOD001
                % (boundary, content_type, len(response.payload), response.payload)
            )
            await send({"type": "http.response.body", "body": body, "more_body": True})

        for index, attachment in enumerate(response.files):
            async with attachment.stream(executor=self._executor) as reader:
                iterator = _internal.aiter_(reader)
                try:
                    data = await _internal.anext_(iterator)
                except StopAsyncIteration:
                    data = b""

                mimetype = reader.mimetype.encode() if reader.mimetype else _OCTET_STREAM_CONTENT_TYPE
                filename = urllib.parse.quote(reader.filename, "").encode()
                body = (
                    b'\r\n--%b\r\nContent-Disposition: form-data; name="files[%i]";'  # noqa: MOD001
                    b'filename="%b"\r\nContent-Type: %b\r\n\r\n%b'  # noqa: MOD001
                    % (boundary, index, filename, mimetype, data)
                )
                await send({"type": "http.response.body", "body": body, "more_body": True})

                async for chunk in iterator:
                    await send({"type": "http.response.body", "body": chunk, "more_body": True})

        await send({"type": "http.response.body", "body": b"\r\n--%b--" % boundary, "more_body": False})  # noqa: MOD001


def _content_type(response: hikari.api.Response, /) -> typing.Optional[bytes]:
    if response.content_type:
        if response.charset:
            return f"{response.content_type}; charset={response.charset}".encode()

        return response.content_type.encode()

    return None  # MyPy


def _find_headers(
    scope: asgiref.HTTPScope, /
) -> tuple[typing.Optional[bytes], typing.Optional[bytes], typing.Optional[bytes]]:
    content_type: typing.Optional[bytes] = None
    signature: typing.Optional[bytes] = None
    timestamp: typing.Optional[bytes] = None
    for name, value in scope["headers"]:
        # As per-spec these should be matched case-insensitively.
        name = name.lower()
        if name == _X_SIGNATURE_ED25519_HEADER:
            signature = bytes.fromhex(value.decode("ascii"))

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

    return content_type, signature, timestamp


class AsgiBot(hikari.RESTBotAware):
    """Bot implementation which acts as an ASGI adapter.

    This bot doesn't initiate a server internally but instead
    relies on being called as an ASGI app.

    For this to work, hikari has to be installed with the optional "server"
    feature (e.g `python -m pip install hikari[server]`).
    """

    __slots__: collections.Sequence[str] = (
        "_adapter",
        "_entity_factory",
        "_executor",
        "_http_settings",
        "_is_alive",
        "_is_asgi_managed",
        "_join_event",
        "_on_shutdown",
        "_on_startup",
        "_proxy_settings",
        "_rest",
    )

    @typing.overload
    def __init__(
        self,
        token: hikari.api.TokenStrategy,
        *,
        public_key: typing.Union[bytes, str, None] = None,
        asgi_managed: bool = True,
        executor: typing.Optional[concurrent.futures.Executor] = None,
        http_settings: typing.Optional[hikari.impl.HTTPSettings] = None,
        max_body_size: int = 1024**2,
        max_rate_limit: float = 300.0,
        max_retries: int = 3,
        proxy_settings: typing.Optional[hikari.impl.ProxySettings] = None,
        rest_url: typing.Optional[str] = None,
    ) -> None:
        ...

    @typing.overload
    def __init__(
        self,
        token: str,
        token_type: typing.Union[str, hikari.TokenType],
        public_key: typing.Union[bytes, str, None] = None,
        *,
        asgi_managed: bool = True,
        executor: typing.Optional[concurrent.futures.Executor] = None,
        http_settings: typing.Optional[hikari.impl.HTTPSettings] = None,
        max_body_size: int = 1024**2,
        max_rate_limit: float = 300.0,
        max_retries: int = 3,
        proxy_settings: typing.Optional[hikari.impl.ProxySettings] = None,
        rest_url: typing.Optional[str] = None,
    ) -> None:
        ...

    def __init__(
        self,
        token: typing.Union[str, hikari.api.TokenStrategy],
        token_type: typing.Union[hikari.TokenType, str, None] = None,
        public_key: typing.Union[bytes, str, None] = None,
        *,
        asgi_managed: bool = True,
        executor: typing.Optional[concurrent.futures.Executor] = None,
        http_settings: typing.Optional[hikari.impl.HTTPSettings] = None,
        max_body_size: int = 1024**2,
        max_rate_limit: float = 300.0,
        max_retries: int = 3,
        proxy_settings: typing.Optional[hikari.impl.ProxySettings] = None,
        rest_url: typing.Optional[str] = None,
    ) -> None:
        """Initialise a new ASGI bot.

        Parameters
        ----------
        token
            The bot or bearer token. If no token is to be used,
            this can be undefined.
        token_type
            The type of token in use. This should only be passed when `str`
            is passed for `token`, can be `"Bot"` or `"Bearer"` and will be
            defaulted to `"Bearer"` in this situation.

            This should be left as [None][] when either
            [hikari.api.rest.TokenStrategy][] or [None][] is passed for
            `token`.
        asgi_managed
            Whether this bot's internal components should be automatically
            started and stopped based on the Asgi lifespan events.
        executor
            If non-[None][], then this executor is used instead of the
            [concurrent.futures.ThreadPoolExecutor][] attached to the
            [asyncio.AbstractEventLoop][] that the bot will run on. This
            executor is used primarily for file-IO.

            While mainly supporting the [concurrent.futures.ThreadPoolExecutor][]
            implementation in the standard lib, Hikari's file handling systems
            should also work with [concurrent.futures.ProcessPoolExecutor][], which
            relies on all objects used in IPC to be `pickle`able. Many third-party
            libraries will not support this fully though, so your mileage may vary
            on using ProcessPoolExecutor implementations with this parameter.
        http_settings
            Optional custom HTTP configuration settings to use. Allows you to
            customise functionality such as whether SSL-verification is enabled,
            what timeouts `aiohttp` should expect to use for requests, and behavior
            regarding HTTP-redirects.
        max_body_size
            The maximum body size this should allow received request bodies to be
            in bytes before failing the request with a 413 - Content Too Large.
        max_rate_limit
            The max number of seconds to backoff for when rate limited. Anything
            greater than this will instead raise an error.

            This defaults to five minutes to stop potentially indefinitely waiting
            on an endpoint, which is almost never what you want to do if giving
            a response to a user.

            You can set this to `float("inf")` to disable this check entirely.
            Note that this only applies to the REST API component that communicates
            with Discord, and will not affect sharding or third party HTTP endpoints
            that may be in use.
        max_retries
            Maximum number of times a request will be retried if

            it fails with a `5xx` status. Defaults to 3 if set to [None][].
        proxy_settings
            Custom proxy settings to use with network-layer logic
            in your application to get through an HTTP-proxy.
        public_key
            The public key to use to verify received interaction requests.

            This may be a hex encoded `str` or the raw `bytes`.
            If left as [None][] then the client will try to work this value
            out based on `token`.
        rest_url
            Defaults to the Discord REST API URL if [None][]. Can be
            overridden if you are attempting to point to an unofficial endpoint, or
            if you are attempting to mock/stub the Discord API for any reason.

            Generally you do not want to change this.

        Raises
        ------
        ValueError
            * If `token_type` is provided when a token strategy is passed for `token`.
            * if `token_type` is left as [None][] when a string is passed for `token`.
        """
        if isinstance(public_key, str):
            public_key = bytes.fromhex(public_key)

        self._entity_factory = hikari.impl.EntityFactoryImpl(self)
        self._executor = executor
        self._http_settings = http_settings or hikari.impl.HTTPSettings()
        self._is_alive = False
        self._join_event: typing.Optional[asyncio.Event] = None
        self._on_shutdown: dict[
            collections.Callable[[Self], collections.Coroutine[typing.Any, typing.Any, typing.Any]],
            collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, typing.Any]],
        ] = {}
        self._on_startup: dict[
            collections.Callable[[Self], collections.Coroutine[typing.Any, typing.Any, typing.Any]],
            collections.Callable[[], collections.Coroutine[typing.Any, typing.Any, typing.Any]],
        ] = {}
        self._proxy_settings = proxy_settings or hikari.impl.ProxySettings()
        self._rest = hikari.impl.RESTClientImpl(
            cache=None,
            entity_factory=self._entity_factory,
            executor=executor,
            http_settings=self._http_settings,
            max_rate_limit=max_rate_limit,
            proxy_settings=self._proxy_settings,
            rest_url=rest_url,
            token=token,
            token_type=token_type,
            max_retries=max_retries,
        )
        self._adapter = AsgiAdapter(
            hikari.impl.InteractionServer(
                entity_factory=self._entity_factory, rest_client=self._rest, public_key=public_key
            ),
            executor=executor,
            max_body_size=max_body_size,
        )

        self._is_asgi_managed = asgi_managed
        if asgi_managed:
            self._adapter.add_startup_callback(self._start)
            self._adapter.add_shutdown_callback(self._close)

    @property
    def entity_factory(self) -> hikari.api.EntityFactory:
        return self._entity_factory

    @property
    def executor(self) -> typing.Optional[concurrent.futures.Executor]:
        return self._executor

    @property
    def http_settings(self) -> hikari_config.HTTPSettings:
        return self._http_settings

    @property
    def interaction_server(self) -> hikari.api.InteractionServer:
        return self._adapter.server

    @property
    def is_alive(self) -> bool:
        return self._is_alive

    @property
    def on_shutdown(
        self,
    ) -> collections.Sequence[collections.Callable[[Self], collections.Coroutine[typing.Any, typing.Any, None]]]:
        return list(self._on_shutdown)

    @property
    def on_startup(
        self,
    ) -> collections.Sequence[collections.Callable[[Self], collections.Coroutine[typing.Any, typing.Any, None]]]:
        return list(self._on_startup)

    @property
    def proxy_settings(self) -> hikari_config.ProxySettings:
        return self._proxy_settings

    @property
    def rest(self) -> hikari.api.RESTClient:
        return self._rest

    async def __call__(
        self, scope: asgiref.Scope, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable, /
    ) -> None:
        """Call the bot with an ASGI event.

        !!! note
            This method is called by the ASGI server and allows the bot to
            function like [AsgiAdapter][yuyo.asgi.AsgiAdapter].

        Parameters
        ----------
        scope
            The scope of the request.
        receive
            The receive function to use.
        send
            The send function to use.

        Raises
        ------
        NotImplementedError
            If this is called with a websocket scope.
        RuntimeError
            If an invalid scope event is passed.
        """
        return await self._adapter(scope, receive, send)

    def run(self) -> None:
        r"""Start the bot's REST client and wait until the bot's closed.

        !!! warning
            Unless `asgi_managed=False` is passed to
            [AsgiBot.\_\_init\_\_][yuyo.asgi.AsgiBot.__init__], the bot will be
            automatically started and closed based on the ASGI lifespan events
            and any other calls to this function will raise a [RuntimeError][].

        Raises
        ------
        RuntimeError
            If the client is already alive.
            If the client is ASGI managed.
        """
        if self._is_asgi_managed:
            raise RuntimeError("The client is being managed by ASGI lifespan events")

        if self._is_alive:
            raise RuntimeError("The client is already running")

        try:
            loop = asyncio.get_running_loop()

        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.start())
        loop.run_until_complete(self.join())

    async def _start(self) -> None:
        self._join_event = asyncio.Event()
        self._is_alive = True
        self._rest.start()

    async def start(self) -> None:
        r"""Start the bot's REST client.

        !!! warning
            Unless `asgi_managed=False` is passed to
            [AsgiBot.\_\_init\_\_][yuyo.asgi.AsgiBot.__init__], the bot will be
            automatically started based on the ASGI lifespan events and any
            other calls to this function will raise a [RuntimeError][].

        Raises
        ------
        RuntimeError
            If the client is already alive.
            If the client is ASGI managed.
        """
        if self._is_asgi_managed:
            raise RuntimeError("The client is being managed by ASGI lifespan events")

        if self._is_alive:
            raise RuntimeError("The client is already running")

        await self._start()

    async def _close(self) -> None:
        assert self._join_event is not None
        self._is_alive = False
        await self._rest.close()
        self._join_event.set()
        self._join_event = None

    async def close(self) -> None:
        """Close the bot's REST client.

        !!! warning
            Unless `asgi_managed=False` is passed to `AsgiBot.__init__`,
            the bot will be automatically closed based on the ASGI lifespan
            events and any other calls to this function will raise a
            [RuntimeError][].

        Raises
        ------
        RuntimeError
            If the client isn't alive.
            If the client is ASGI managed.
        """
        if self._is_asgi_managed:
            raise RuntimeError("The client is being managed by ASGI lifespan events")

        if not self._is_alive or not self._join_event:
            raise RuntimeError("The client is not running")

        await self._close()

    async def join(self) -> None:
        if self._join_event is None:
            raise RuntimeError("The client is not running")

        await self._join_event.wait()

    def add_shutdown_callback(
        self, callback: collections.Callable[[Self], collections.Coroutine[typing.Any, typing.Any, None]], /
    ) -> None:
        """Add a callback to be called when the bot shuts down.

        !!! warning
            These callbacks will block the bot from shutting down until
            they complete and any raised errors will lead to a failed shutdown.

        Parameters
        ----------
        callback
            The shutdown callback to add.
        """
        if callback in self._on_shutdown:
            return

        async def shutdown_callback() -> None:
            await callback(self)

        self._on_shutdown[callback] = shutdown_callback
        self._adapter.add_shutdown_callback(shutdown_callback)

    def remove_shutdown_callback(
        self, callback: collections.Callable[[Self], collections.Coroutine[typing.Any, typing.Any, None]], /
    ) -> None:
        """Remove a shutdown callback.

        Parameters
        ----------
        callback
            The shutdown callback to remove.

        Raises
        ------
        ValueError
            If the callback was not registered.
        """
        try:
            registered_callback = self._on_shutdown.pop(callback)

        except KeyError:
            pass

        else:
            self._adapter.remove_shutdown_callback(registered_callback)

    def add_startup_callback(
        self, callback: collections.Callable[[Self], collections.Coroutine[typing.Any, typing.Any, None]], /
    ) -> None:
        """Add a callback to be called when the bot starts up.

        !!! warning
            These callbacks will block the bot from starting until they
            complete and any raised errors will lead to a failed startup.

        Parameters
        ----------
        callback
            The startup callback to add.
        """
        if callback in self._on_startup:
            return

        async def startup_callback() -> None:
            await callback(self)

        self._on_startup[callback] = startup_callback
        self._adapter.add_startup_callback(startup_callback)

    def remove_startup_callback(
        self, callback: collections.Callable[[Self], collections.Coroutine[typing.Any, typing.Any, None]], /
    ) -> None:
        """Remove a startup callback.

        Parameters
        ----------
        callback
            The startup callback to remove.

        Raises
        ------
        ValueError
            If the callback was not registered.
        """
        try:
            registered_callback = self._on_startup.pop(callback)

        except KeyError:
            pass

        else:
            self._adapter.remove_startup_callback(registered_callback)
