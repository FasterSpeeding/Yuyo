# Modals

Modals allow bots to prompt a user for more information as the initial response
for a slash command, context menu or message component interaction.

![modal example](./images/modal_example.png)

Modals take the shape of dialogue boxes which show up on top of everything for
the user who triggered the relevant interaction (as shown above) and only
support text input right now.

### Declaring Modals

There's several different ways to declare modals using Yuyo:

##### Modal classes

When working with modal classes you'll be adding "static" fields which are
included on every instance of the modal class. There's a couple of ways to
declare these:

```py
--8<-- "./docs_src/modals.py:27:36"
```

Subclassing [Modal][yuyo.modals.Modal] lets you create a unique modal template.
`Modal` subclasses will never inherit fields.

You can define the fields that'll appear on all instances of a modal template
by setting field descriptors as argument defaults for the modal's callback
(as shown above).

The following descriptors are supported:

* [text_input][yuyo.modals.text_input]

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
--8<-- "./docs_src/modals.py:49:54"
```

[as_modal_template][yuyo.modals.as_modal_template] provides a short hand for
creating a [Modal][yuyo.modals.Modal] subclass from a callback.

##### Modal instances

```py
--8<-- "./docs_src/modals.py:58:62"
```

```py
--8<-- "./docs_src/modals.py:66:73"
```

[as_modal][yuyo.modals.as_modal] and [modal][yuyo.modals.modal] both provide
ways to create instances of modals from a callback.

These only support the signature field descriptors and modal dataclasses when
`parse_signature=True` is explicitly passed.

##### Modal dataclass

```py
--8<-- "./docs_src/modals.py:77:85"
```

Another aspect of signature parsing is [ModalOptions][yuyo.modals.ModalOptions].
This is a dataclass of modal fields which supports declaring said fields by
using the same descriptors listed earlier as class variables.

To use this dataclass with a modal you then have to use it as a modal

This supports inheriting fields from other modal options dataclasses (including
mixed inheritance) but does not support slotting nor custom `__init__`s.

### Handling Modal Interactions

There's two main ways to handle modal interactions with Yuyo:

##### Stateful

```py
--8<-- "./docs_src/modals.py:89:102"
```

Subclassing [Modal][yuyo.modals.Modal] let you associate state with a specific
modal execution through OOP.

When doing this you'll usually be creating an instance of the modal per
interaction and associating this with a specific modal execution by using
the parent interaction's custom ID as the modal's custom ID (as shown above).

[ModalClient.register_modal][yuyo.modals.ModalClient.register_modal] defaults
`timeout` to a 30 second one use timeout.

##### Stateless

```py
--8<-- "./docs_src/modals.py:106:122"
```

Alternatively, modals can be reused by using a global custom ID and registering the
modal to the client on startup with `timeout=None` and sending the same modal's
rows per-execution.

Custom IDs have some special handling which allows you to track some metadata
for specific modal executions. Custom IDs are split into two parts as
`"{match}:{metadata}"` where the "match" part is what Yuyo will use to find the
executor for a modal call and the "metadata"
([ModalContext.id_metadata][yuyo.components.BaseContext.id_metadata]) part
represents any developer added metadata for the modal.

If should be noted that Custom IDs can never be longer than 100 characters in
total length.
