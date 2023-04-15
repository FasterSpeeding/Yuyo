# Asgi

The [AsgiBot][yuyo.asgi.AsgiBot] is a [RESTBot][hikari.traits.RESTBotAware]
implementation which acts as an ASGI application which will handle the
interaction requests received from Discord for slash commands, context menus,
message components and modals as part of an ASGI server.

```py
--8<-- "./docs_src/asgi.py:23:26"
```

If the above example was saved in the file "bot.py"
(within the current working directory) then the following may be run in the command
line to run this bot using [Uvicorn](https://www.uvicorn.org/):

```
uvicorn bot:rest_bot
```

But since ASGI is a generic standard, you can also run this bot in other
tooling such as [Hypercorn](https://pgjones.gitlab.io/hypercorn/),
[Daphne](https://github.com/django/daphne),
or using [FastAPI](https://fastapi.tiangolo.com/)'s
[sub-applications](https://fastapi.tiangolo.com/advanced/sub-applications/)
to mount this bot on a specific route within an existing FastAPI server:

```py
--8<-- "./docs_src/asgi.py:30:34"
```

The extra steps this example goes through to let FastAPI startup and shutdown
the [AsgiBot][yuyo.asgi.AsgiBot] are only necessary when mounting as a FastAPI
sub-application.

#### Serverless

```py
--8<-- "./docs_src/asgi.py:38:42"
```

Thanks to the flexibility of the ASGI standard, this can also be used with
serverless frameworks people have implemented ASGI adapters for. The above
example uses [agraffe](https://pypi.org/project/agraffe/) to create an entry
point for AWS Lambdas, Azure Functions, or Google Cloud Functions.
