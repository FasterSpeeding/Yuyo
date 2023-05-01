# Modals

Modals allow bots to prompt a user for more information as the initial response
for a slash command, context menu or message component interaction.

![modal example](./images/modal_example.png)

Modals take the shape of dialogue boxes which show up on top of everything for
the user who triggered the relevant interaction (as shown above).

### Making a Modal client

The Modal client keeps track of registered modals and handles executing them.

This can be created with any of the following class methods:

* [ModalClient.from_gateway_bot][yuyo.modals.ModalClient.from_gateway_bot]:
    Create a modal client from a Hikari gateway bot (i.e.
    [hikari.GatewayBot][hikari.impl.gateway_bot.GatewayBot]).
* [ModalClient.from_rest_bot][yuyo.modals.ModalClient.from_rest_bot]:
    Create a modal client from a Hikari REST bot (i.e.
    [hikari.RESTBot][hikari.impl.rest_bot.RESTBot] or [yuyo.asgi.AsgiBot][]).
* [ModalClient.from_tanjun][yuyo.modals.ModalClient.from_tanjun]:
    Create a modal client from a Tanjun [Client][tanjun.abc.Client].

    This method will make the modal client use  Tanjun's Alluka client for
    dependency injection, essentially mirroring the dependencies registered
    for Tanjun's DI while also registering
    [ModalClient][yuyo.modals.ModalClient] as a type dependency.

Client state can be managed through dependency injection. This is implemented using
[Alluka][alluka] and more information about it can be found in Alluka's
[usage guide](https://alluka.cursed.solutions/usage/). The Alluka client
used for modal execution can be found at
[ComponentClient.alluka][yuyo.components.ComponentClient.alluka].

For the sake of simplicity, the following examples all assume the modal client
can be accessed through Alluka style dependency injection.

### Declaring Modals

The only field type supported for modals right now are text inputs.

A modal can have up to 5 text inputs in it and there are two different
flavours of text inputs: the default "sentence" style which only lets
users input a single line of text and the "paragraph" style which
allows multiple lines of text.

There's several different ways to declare modals using Yuyo:

##### Subclasses

When working with modal classes you'll be adding "static" fields which are
included on every instance of the modal class. There's a couple of ways to
declare these:

```py
--8<-- "./docs_src/modals.py:27:36"
```

Subclassing [Modal][yuyo.modals.Modal] lets you create a unique modal template.
`Modal` subclasses will never inherit fields. The modal's execution callback
must always be called `callback` when subclassing.

You can define the fields that'll appear on all instances of a modal template
by setting field descriptors as argument defaults for the modal's callback
(as shown above).

The following descriptors are supported:

* [text_input][yuyo.modals.text_input]

!!! warning
    If you declare `__init__` on a [Modal][yuyo.modals.Modal] subclass
    then you must make sure to first call `super().__init__()` in it.

```py
--8<-- "./docs_src/modals.py:40:45"
```

You can also define the template's fields by manually calling the `add_static_{}`
class methods either directly or through one of the provided `with_static_{}`
decorator functions. Note that decorators are executed from the bottom upwards
and this will be reflected in the order of these fields.

When using this approach the field's value/default will only be passed to the
callback if you explicitly pass the relevant argument's name as `parameter=` to
the add (class) method.

```py
--8<-- "./docs_src/modals.py:49:52"
```

[as_modal_template][yuyo.modals.as_modal_template] provides a short hand for
creating a [Modal][yuyo.modals.Modal] subclass from a callback.

##### Instances

```py
--8<-- "./docs_src/modals.py:56:60"
```

```py
--8<-- "./docs_src/modals.py:64:71"
```

[as_modal][yuyo.modals.as_modal] and [modal][yuyo.modals.modal] both provide
ways to create instances of modals from a callback.

These only support the signature field descriptors and modal dataclasses when
`parse_signature=True` is explicitly passed.

##### Options Dataclass

```py
--8<-- "./docs_src/modals.py:75:83"
```

Another aspect of signature parsing is [ModalOptions][yuyo.modals.ModalOptions].
This is a dataclass of modal fields which supports declaring said fields by
using the same descriptors listed earlier as class variables.

To use this dataclass with a modal you then have to use it as type-hint for
one of the modal callback's arguments.

This supports inheriting fields from other modal options dataclasses (including
mixed inheritance) but does not support slotting nor custom `__init__`s.

### Handling Modal Interactions

There's two main ways to handle modal interactions with Yuyo:

##### Stateful

```py
--8<-- "./docs_src/modals.py:87:101"
```

Subclassing [Modal][yuyo.modals.Modal] let you associate state with a specific
modal execution through OOP.

When doing this you'll usually be creating an instance of the modal per
interaction and associating this with a specific modal execution by using
the parent interaction's custom ID as the modal's custom ID (as shown above).

[ModalClient.register_modal][yuyo.modals.ModalClient.register_modal] defaults
`timeout` to a 2 minute one use timeout.

##### Stateless

```py
--8<-- "./docs_src/modals.py:105:121"
```

Alternatively, modals can be reused by using a global custom ID and registering the
modal to the client on startup with `timeout=None` and sending the same modal's
rows per-execution.

Custom IDs have some special handling which allows you to track some metadata
for specific modal executions. They are split into two parts as
`"{match}:{metadata}"`, where the "match" part is what Yuyo will use to find
the executor for a modal call and the "metadata"
([ModalContext.id_metadata][yuyo.components.BaseContext.id_metadata]) part
represents any developer added metadata for that instance of the modal.

If should be noted that Custom IDs can never be longer than 100 characters in
total length.

### Responding to Modals

```py
--8<-- "./docs_src/modals.py:125:130"
```

[ModalContext.respond][yuyo.components.BaseContext.respond] is used to
respond to an interaction with a new message, this has a similar signature
to Hikari's message respond method but will only be guaranteed to return a
[hikari.Message][hikari.messages.Message] object when `ensure_result=True` is
passed.

!!! note
    You cannot create another modal prompt in response to a modal interaction.

##### Ephemeral responses

```py
--8<-- "./docs_src/modals.py:134:137"
```

Ephemeral responses mark the response message as private (so that only the
author can see it) and temporary. A response can be marked as ephemeral by
passing `ephemeral=True` to either
[ModalContext.create_initial_response][yuyo.modals.ModalContext.create_initial_response]
(when initially responding to the interaction) or
[ModalContext.create_followup][yuyo.components.BaseContext.create_followup]
(for followup responses).

##### Deferrals

Interactions need an initial response within 3 seconds but, if you can't give a
response within 3 seconds, you can defer the first response using
[ModalContext.defer][yuyo.modals.ModalContext.defer].

A deferral should then be finished by editing in the initial response using either
[ModalContext.edit_initial_response][yuyo.components.BaseContext.edit_initial_response]
or [ModalContext.respond][yuyo.components.BaseContext.respond] and if you
want a response to be ephemeral then you'll have to pass `ephemeral=True` when
deferring.
