# Builders

Yuyo provides several methods for converting Hikari data objects to writeable
builder objects.

### Commands

```py
--8<-- "./docs_src/builders.py:19:19"
```

[to_cmd_builder][yuyo.to_builder.to_cmd_builder] converts a
[hikari.PartialCommand][hikari.commands.PartialCommand] object to the relevant
builder object.

[to_slash_cmd_builder][yuyo.to_builder.to_slash_cmd_builder] and
[to_context_menu_builder][yuyo.to_builder.to_context_menu_builder] can be used
to convert command objects where the command type is already known without
losing this information typing wise.

### Message components

```py
--8<-- "./docs_src/builders.py:23:23"
```

[to_msg_action_row_builder][yuyo.to_builder.to_msg_action_row_builder] converts
a [hikari.MessageActionRowComponent][hikari.components.MessageActionRowComponent]
object to a
[hikari.api.MessageActionRowBuilder][hikari.api.special_endpoints.MessageActionRowBuilder]
object.

There's several other methods which can be used to convert the sub-component
objects found in message action rows to builder objects:

* [to_select_menu_builder][yuyo.to_builder.to_select_menu_builder]
* [to_channel_select_menu_builder][yuyo.to_builder.to_channel_select_menu_builder]
* [to_text_select_menu_builder][yuyo.to_builder.to_text_select_menu_builder]
* [to_button_builder][yuyo.to_builder.to_button_builder]
