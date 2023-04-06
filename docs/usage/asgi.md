# Asgi

The [AsgiBot][yuyo.asgi.AsgiBot] acts as an ASGI application which will handle
the interaction requests received from Discord for slash commands, context menus,
message components and modals as part of an ASGI server.

```py
--8<-- "./docs_src/asgi.py:11:20"
```

If the above example was saved in the file "bot.py"
(within the current working directory) then the following may be run in the command
line to run this bot using [Uvicorn](https://www.uvicorn.org/):

```
uvicorn bot:bot
```

But since ASGI is a generic standard, you can also run this bot in other tooling
such as using [FastAPI](https://fastapi.tiangolo.com/)'s
[sub-applications](https://fastapi.tiangolo.com/advanced/sub-applications/) to
mount this bot within an existing FastAPI server on a specific route:

```py
--8<-- "./docs_src/asgi.py:22:26"
```