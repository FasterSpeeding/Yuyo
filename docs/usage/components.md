# Message Components

Message components are the interactive buttons and select menus you'll see on
some messages sent by bots.

### Types of components

##### Buttons

![button colours](./images/button_colours.png)

Message buttons have several different styles, as shown above. Most of these
are interactive, meaning that an interaction will be sent to the bot when a
user clicks on it. The only non-interactive style being link buttons, which
simply open the set link in a browser for the user who clicked on it.

A row can have up to 5 buttons in it.

### Select Menus

![select menu example](./images/select_menu_example.png)

Select menus let users select between 0 to 25 options (dependent on how the bot
configured it). These selections are communicated to the bot once the user has
finished selecting options via and interaction and there's several different
resources they can be selecting:

* Text menus: lets the bot pre-define up to 25 text options
* User menus: lets the user pick up to 25 users
* Role menus: lets the user pick up to 25 roles
* Channel menus: lets the user pick up to 25 channels
* Mentionable menus: lets the user pick up to 25 roles and users

!!! note
    As of writing user, role, channel and mentionable menus only let you select
    entities from the current guild. Only text menus working properly in DM
    channels.

Each select menu takes up a whole row.

### Declaring Components

When adding sub-components to a select menu, they'll either be appended to the
last row or they'll be added to a new row if the new entry wouldn't fit in the
last row.

A message can only have up to 5 component rows on it.

There's several different ways to declare components using Yuyo:

### Subclassing

```py
--8<-- "./docs_src/components.py:30:53"
```

When subclassing [ActionColumnExecutor][yuyo.components.ActionColumnExecutor],
you can use any of the following class descriptors to add "static"
sub-components (which'll be included on every instance and subclass of the
column) to it:

* [as_channel_menu][yuyo.components.as_channel_menu]
* [as_interactive_button][yuyo.components.as_interactive_button]
* [as_select_menu][yuyo.components.as_select_menu]
* [as_text_menu][yuyo.components.as_text_menu]
* [link_button][yuyo.components.link_button]

```py
--8<-- "./docs_src/components.py:57:62"
```

Most of these descriptors decorate a callback which'll be called when that
specific sub-component is used by a user, with the only exception being
link buttons which open a link for the user instead of sending an interaction
to the bot.

```py
--8<-- "./docs_src/components.py:66:80"
```

Alternatively, static sub-components can be added to an
[ActionColumnExecutor][yuyo.components.ActionColumnExecutor] subclass using the
`add_static_{}` class methods or the relevant `with_static_{}` class decorator
functions.

### Builder

```py
--8<-- "./docs_src/components.py:85:96"
```

```py
--8<-- "./docs_src/components.py:101:105"
```

You can also dynamically build a
[ActionColumnExecutor][yuyo.components.ActionColumnExecutor] after initialising
it by using the chainable `add_{}` methods it provides to add sub-components.

### Handling Component Interactions

There's two main ways to handle component interactions with Yuyo:

##### Stateful

```py
--8<-- "./docs_src/components.py:109:124"
```

Subclassing [ActionColumnExecutor][yuyo.components.ActionColumnExecutor] allows
you to associate state with a specific message's components through OOP.

When doing this you'll usually be creating an instance of the components column
per message.

[ComponentClient.register_executor][yuyo.components.ComponentClient.register_executor]
defaults `timeout` to a 30 second sliding timeout (meaning that the timer
resets every use).

##### Stateless

```py
--8<-- "./docs_src/components.py:128:144"
```

Alternatively, components can be reused by registering the modal to the client
on startup with `timeout=None` and sending the same modal's rows per-exevution.

Custom IDs have some special handling which allows you to track some metadata
for a specific message's components. Custom IDs are split into two parts as
`"{match}:{metadata}"` where the "match" part is what Yuyo will use to find the
executor for a message's components and the "metadata"
([ComponentContext.id_metadata][yuyo.components.BaseContext.id_metadata]) part
represents any developer added metadata for that specific component.

It should be noted that interactive components should be given constant custom
IDs when using an action column statelessly and that Custom IDs can never be
longer than 100 characters in total length.
