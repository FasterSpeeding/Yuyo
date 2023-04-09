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

### Select Menus

![select menu example](./images/select_menu_example.png)

Select menus let users select between 0 to 25 options (dependent on how the bot
configured it). These selections are communicated to the bot once the user has
finished selecting options via and interaction and there's several different
resources they can be selecting:

* Text menus: lets the bot pre-define up to 25 text options
* User menus: lets the user pick up to 25 users (in the current guild)?
* Role menus: lets the user pick up to 25 roles (in the current guild)?
* Channel menus: lets the user pick up to 25 of the current guild's channels
* Mentionable menus: lets the user pick up to 25 roles and users (in the current guild)?

### Declaring Components

There's several different ways to declare components using Yuyo:

```py
--8<-- "./docs_src/components.py:26:46"
```

```py
--8<-- "./docs_src/components.py:50:55"
```

### Handling Component Interactions

##### Stateful

```py
--8<-- "./docs_src/components.py:59:74"
```

Subclassing [ActionColumnExecutor][yuyo.components.ActionColumnExecutor] allows
you to associate state with a specific message's components through OOP.

When doing this you'll usually be creating an instance of the components column
per message.

##### Stateless

```py
--8<-- "./docs_src/components.py:78:94"
```

Alternatively, components can be reused by registering the modal to the client
on startup with `timeout=None` and sending the same modal's rows per-exevution.

Custom IDs have some special handling which allows you to track some metadata
for a specific message's components. Custom IDs are split into two parts as
`"{match}:{metadata}"` where the "match" part is what Yuyo wil use to find the
executor for a message's components and the "metadata"
([ComponentContext.id_metadata][yuyo.components.BaseContext.id_metadata]) part
represents any developer added metadata for that specific component.

It should be noted that interactive components should be given constant custom
IDs when using an action column statelessly and that Custom IDs can never be
longer than 100 characters in total length.
