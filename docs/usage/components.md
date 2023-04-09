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
conigured it). These selections are communicated to the bot once the user has
finished selecting options via and interaction and there's several different
resources they can be selecting:

* Text menus: let the bot pre-define up to 25 options
* User menus: let the user pick up to 25 users (in the current guild)?
* Role menus: let the user pick up to 25 roles (in the current guild)?
* Channel menus: let the user pick up to 25 of the current guild's channels
* Mentionable menus: let the user pick up to 25 roles and users (in the current guild)?

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

Subclassing [yuyo.components.ActionColumnExecutor]

##### Stateless

```py
--8<-- "./docs_src/components.py:78:94"
```
