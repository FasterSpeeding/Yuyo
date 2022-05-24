# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020-2022, Faster Speeding
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

__all__: typing.Sequence[str] = ["AsgiAdapter", "AsgiBot"]

import asyncio
import traceback
import typing

import hikari

if typing.TYPE_CHECKING:
    import concurrent.futures

    import asgiref.typing as asgiref
    from hikari.api import config as hikari_config

_AsgiAdapterT = typing.TypeVar("_AsgiAdapterT", bound="AsgiAdapter")


_CONTENT_TYPE_KEY: typing.Final[bytes] = b"content-type"
_JSON_CONTENT_TYPE: typing.Final[bytes] = b"application/json"
_BAD_REQUEST_STATUS: typing.Final[int] = 400
_X_SIGNATURE_ED25519_HEADER: typing.Final[bytes] = b"x-signature-ed25519"
_X_SIGNATURE_TIMESTAMP_HEADER: typing.Final[bytes] = b"x-signature-timestamp"
_TEXT_CONTENT_TYPE: typing.Final[bytes] = b"text/plain; charset=UTF-8"


async def _error_response(
    send: asgiref.ASGISendCallable, body: bytes, *, status_code: int = _BAD_REQUEST_STATUS
) -> None:
    await send(
        {"type": "http.response.start", "status": status_code, "headers": [(_CONTENT_TYPE_KEY, _TEXT_CONTENT_TYPE)]}
    )
    await send({"type": "http.response.body", "body": body, "more_body": False})


async def _maybe_await(callback: typing.Callable[[], typing.Union[None, typing.Awaitable[None]]]) -> None:
    result = callback()
    if isinstance(result, typing.Awaitable):
        await result


class AsgiAdapter:
    """Asgi/3 adapter for Hikari's interaction server interface."""

    __slots__ = ("_on_shutdown", "_on_startup", "_server")

    def __init__(self, server: hikari.api.InteractionServer, /) -> None:
        """Initialise the adapter.

        Parameters
        ----------
        server : hikari.api.InteractionServer
            The interaction server to use.
        """
        self._on_shutdown: typing.List[typing.Callable[[], typing.Union[None, typing.Awaitable[None]]]] = []
        self._on_startup: typing.List[typing.Callable[[], typing.Union[None, typing.Awaitable[None]]]] = []
        self._server = server

    @property
    def server(self) -> hikari.api.InteractionServer:
        """The interaction server this adapter is bound to."""
        return self._server

    async def __call__(
        self, scope: asgiref.Scope, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable
    ) -> None:
        """Call the adapter.

        .. note::
            This method is called by the ASGI server.

        Parameters
        ----------
        scope : asgiref.Scope
            The scope of the request.
        receive : asgiref.ASGIReceiveCallable
            The receive function to use.
        send : asgiref.ASGISendCallable
            The send function to use.

        Raises
        ------
        NotImplementedError
            If this is called with a websocket scope.
        RuntimeError
            If an invalid scope event is passed.
        """
        if scope["type"] == "http":
            await self.process_request(scope, receive, send)

        elif scope["type"] == "lifespan":
            await self.process_lifespan_event(receive, send)

        else:
            raise NotImplementedError("Websocket operations are not supported")

    def add_shutdown_callback(
        self: _AsgiAdapterT, callback: typing.Callable[[], typing.Union[None, typing.Awaitable[None]]], /
    ) -> _AsgiAdapterT:
        """Add a callback to be called when the ASGI server shuts down.

        .. warning::
            These callbacks will block the ASGI server from shutting down until
            they complete and any raised errors will lead to a failed shutdown.

        Parameters
        ----------
        callback : typing.Callable[[], typing.Union[None, typing.Awaitable[None]]]
            The shutdown callback to add.

        Returns
        -------
        SelfT
            This adapter to enable call chaining.
        """
        self._on_shutdown.append(callback)
        return self

    def add_startup_callback(
        self: _AsgiAdapterT, callback: typing.Callable[[], typing.Union[None, typing.Awaitable[None]]], /
    ) -> _AsgiAdapterT:
        """Add a callback to be called when the ASGI server starts up.

        .. warning::
            These callbacks will block the ASGI server from starting until
            they complete and any raised errors will lead to a failed startup.

        Parameters
        ----------
        callback : typing.Callable[[], typing.Union[None, typing.Awaitable[None]]]
            The startup callback to add.

        Returns
        -------
        SelfT
            This adapter to enable call chaining.
        """
        self._on_startup.append(callback)
        return self

    async def process_lifespan_event(
        self, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable, /
    ) -> None:
        """Process a lifespan ASGI event.

        .. note::
            This function is used internally by the adapter.

        Parameters
        ----------
        receive : asgiref.ASGIReceiveCallable
            The receive function to use.
        send : asgiref.ASGISendCallable
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
                await asyncio.gather(*map(_maybe_await, self._on_startup))

            except BaseException:
                await send({"type": "lifespan.startup.failed", "message": traceback.format_exc()})

            else:
                await send({"type": "lifespan.startup.complete"})

        elif message_type == "lifespan.shutdown":
            try:
                await asyncio.gather(*map(_maybe_await, self._on_shutdown))

            except BaseException:
                await send({"type": "lifespan.shutdown.failed", "message": traceback.format_exc()})

            else:
                await send({"type": "lifespan.shutdown.complete"})

        else:
            raise RuntimeError(f"Unknown lifespan event {message_type}")

    async def process_request(
        self, scope: asgiref.HTTPScope, receive: asgiref.ASGIReceiveCallable, send: asgiref.ASGISendCallable, /
    ) -> None:
        """Process an HTTP request.

        .. note::
            This function is used internally by the adapter.

        Parameters
        ----------
        scope : asgiref.HTTPScope
            The scope of the request.
        receive : asgiref.ASGIReceiveCallable
            The receive function to use.
        send : asgiref.ASGISendCallable
            The send function to use.
        """
        if scope["method"] != "POST" or scope["path"] != "/":
            await _error_response(send, b"Not found", status_code=404)
            return

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
            await _error_response(send, b"Missing required request signature header(s)")
            return

        try:
            response = await self.server.on_interaction(body, signature, timestamp)
        except Exception:
            await _error_response(send, b"Internal Server Error", status_code=500)
            raise

        headers: typing.List[typing.Tuple[bytes, bytes]] = []
        if response.headers:
            headers.extend((key.encode(), value.encode()) for key, value in response.headers.items())

        await send({"type": "http.response.start", "status": response.status_code, "headers": headers})
        await send({"type": "http.response.body", "body": response.payload or b"", "more_body": False})


class AsgiBot(AsgiAdapter, hikari.RESTBotAware):
    """Bot implementation which acts as an ASGI adapter.

    This bot doesn't initiate a server internally but instead
    relies on being called as an ASGI app.
    """

    __slots__: typing.Sequence[str] = (
        "_entity_factory",
        "_executor",
        "_http_settings",
        "_is_alive",
        "_is_asgi_managed",
        "_join_event",
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
        max_rate_limit: float = 300.0,
        max_retries: int = 3,
        proxy_settings: typing.Optional[hikari.impl.ProxySettings] = None,
        rest_url: typing.Optional[str] = None,
    ) -> None:
        """Initialise a new ASGI bot.

        Parameters
        ----------
        token : typing.Union[str, None, hikari.api.rest.TokenStrategy]
            The bot or bearer token. If no token is to be used,
            this can be undefined.
        token_type : typing.Union[str, hikari.applications.TokenType, None]
            The type of token in use. This should only be passed when `str`
            is passed for `token`, can be `"Bot"` or `"Bearer"` and will be
            defaulted to `"Bearer"` in this situation.

            This should be left as `None` when either
            `hikari.api.rest.TokenStrategy` or `None` is passed for
            `token`.

        Other Parameters
        ----------------
        asgi_managed: bool
            Whether this bot's internal components should be automatically
            started and stopped based on the Asgi lifespan events.

            Defaults to `True`.
        executor : typing.Optional[concurrent.futures.Executor]
            Defaults to `builns.None`. If non-`None`, then this executor
            is used instead of the `concurrent.futures.ThreadPoolExecutor` attached
            to the `asyncio.AbstractEventLoop` that the bot will run on. This
            executor is used primarily for file-IO.

            While mainly supporting the `concurrent.futures.ThreadPoolExecutor`
            implementation in the standard lib, Hikari's file handling systems
            should also work with `concurrent.futures.ProcessPoolExecutor`, which
            relies on all objects used in IPC to be `pickle`able. Many third-party
            libraries will not support this fully though, so your mileage may vary
            on using ProcessPoolExecutor implementations with this parameter.
        http_settings : typing.Optional[hikari.config.HTTPSettings]
            Optional custom HTTP configuration settings to use. Allows you to
            customise functionality such as whether SSL-verification is enabled,
            what timeouts `aiohttp` should expect to use for requests, and behavior
            regarding HTTP-redirects.
        max_rate_limit : float
            The max number of seconds to backoff for when rate limited. Anything
            greater than this will instead raise an error.

            This defaults to five minutes if left to the default value. This is to
            stop potentially indefinitely waiting on an endpoint, which is almost
            never what you want to do if giving a response to a user.

            You can set this to `float("inf")` to disable this check entirely.
            Note that this only applies to the REST API component that communicates
            with Discord, and will not affect sharding or third party HTTP endpoints
            that may be in use.
        max_retries : typing.Optional[int]
            Maximum number of times a request will be retried if

            it fails with a `5xx` status. Defaults to 3 if set to `None`.
        proxy_settings : typing.Optional[hikari.config.ProxySettings]
            Custom proxy settings to use with network-layer logic
            in your application to get through an HTTP-proxy.
        public_key : typing.Union[str, bytes, None]
            The public key to use to verify received interaction requests.

            This may be a hex encoded `str` or the raw `bytes`.
            If left as `None` then the client will try to work this value
            out based on `token`.
        rest_url : typing.Optional[str]
            Defaults to the Discord REST API URL if `None`. Can be
            overridden if you are attempting to point to an unofficial endpoint, or
            if you are attempting to mock/stub the Discord API for any reason.

            Generally you do not want to change this.

        Raises
        ------
        ValueError
            * If `token_type` is provided when a token strategy is passed for `token`.
            * if `token_type` is left as `None` when a string is passed for `token`.
        """
        if isinstance(public_key, str):
            public_key = bytes.fromhex(public_key)

        self._entity_factory = hikari.impl.EntityFactoryImpl(self)
        self._executor = executor
        self._http_settings = http_settings or hikari.impl.HTTPSettings()
        self._is_alive = False
        self._join_event: typing.Optional[asyncio.Event] = None
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
        super().__init__(
            hikari.impl.InteractionServer(
                entity_factory=self._entity_factory, rest_client=self._rest, public_key=public_key
            )
        )

        self._is_asgi_managed = asgi_managed
        if asgi_managed:
            self.add_startup_callback(self._start)
            self.add_shutdown_callback(self._close)

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
        return self.server

    @property
    def is_alive(self) -> bool:
        return self._is_alive

    @property
    def proxy_settings(self) -> hikari_config.ProxySettings:
        return self._proxy_settings

    @property
    def rest(self) -> hikari.api.RESTClient:
        return self._rest

    def run(self) -> None:
        """Start the bot's REST client and wait until the bot's closed.

        .. warning::
            Unless `asgi_managed=False` is passed to `AsgiBot.__init__`,
            the bot will be automatically started and closed based on the ASGI
            lifespan events and any other calls to this function will raise a
            `RuntimeError`.

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
        """Start the bot's REST client.

        .. warning::
            Unless `asgi_managed=False` is passed to `AsgiBot.__init__`,
            the bot will be automatically started based on the ASGI
            lifespan events and any other calls to this function will
            raise a `RuntimeError`.

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

        .. warning::
            Unless `asgi_managed=False` is passed to `AsgiBot.__init__`,
            the bot will be automatically closed based on the ASGI lifespan
            events and any other calls to this function will raise a
            `RuntimeError`.

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
