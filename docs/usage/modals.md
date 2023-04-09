# Modals

Modals allow bots to prompt a user for more information as the initial response
for a slash command, context menu or message component interaction.

![modal example](./images/modal_example.png)

Modals take the shape of dialogue boxes which show up on top of everything for
the user who trigered the relevant interaction (as shown above) and only
support text input right now.

### Declaring Modals

There's several different ways to declare modals using Yuyo.

```py
--8<-- "./docs_src/modals.py:27:29"
```

```py
--8<-- "./docs_src/modals.py:33:42"
```

```py
--8<-- "./docs_src/modals.py:46:48"
```

```py
--8<-- "./docs_src/modals.py:52:60"
```

### Handling Modal Interactions

There's two ways to handle modal interactions with Yuyo:

##### Stateful

```py
--8<-- "./docs_src/modals.py:64:71"
```

##### Stateless

```py
--8<-- "./docs_src/modals.py:75:93"
```
