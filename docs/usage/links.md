# Links

Yuyo provides some utilities for handling Discord links in [yuyo.links][].

### BaseLink

There are several [BaseLink][yuyo.links.BaseLink] provided which come with 3
methods for parsing them from strings.

```py
--8<-- "./docs_src/links.py:20:20"
```

[BaseLink.from_link][yuyo.links.BaseLink.from_link] lets you parse a raw link
string. This is strict about validation and will raise a [ValueError][] if the
full passed string isn't a match for the expected link structure.

```py
--8<-- "./docs_src/links.py:24:25"
```

[BaseLink.find][yuyo.links.BaseLink.find] lets you extract the first link in a
string. This will search for a link at any point in the string and returns the
parsed link object or [None][] if no link was found.

```py
--8<-- "./docs_src/links.py:29:30"
```

[BaseLink.find_iter][yuyo.links.BaseLink.find_iter] lets you iterate over the
matching links in a string by iterating over link objects which were parsed
from the string.

### BaseLink implementations

There are 4 implementations of [BaseLink][yuyo.links.BaseLink] provided by
Yuyo (which all support the parsing methods listed above):

##### Invite links

```py
--8<-- "./docs_src/links.py:34:39"
```

[InviteLink][yuyo.links.InviteLink] handles parsing invite links.

```py
--8<-- "./docs_src/links.py:43:44"
```

[links.make_invite_link][yuyo.links.make_invite_link] offers an alternative
way to make an invite link string which doesn't require having a Bot or REST
app in scope.

##### Message links

```py
--8<-- "./docs_src/links.py:48:58"
```

[MessageLink][yuyo.links.MessageLink] handles parsing message links.

[MessageLink.guild_id][yuyo.links.MessageLink.guild_id] will be [None][] for DM messages.

```py
--8<-- "./docs_src/links.py:62:66"
```

[links.make_message_link][yuyo.links.make_message_link] offers an alternative
way to make a message link string which doesn't require having a Bot or REST
app in scope.

##### Guild template links

```py
--8<-- "./docs_src/links.py:70:74"
```

[TemplateLink][yuyo.links.TemplateLink] handles parsing guild template links.

```py
--8<-- "./docs_src/links.py:78:79"
```

[links.make_template_link][yuyo.links.make_template_link] offers an alternative
way to make a template link string which doesn't require having a Bot or REST
app in scope.

##### Webhook links

```py
--8<-- "./docs_src/links.py:83:88"
```

[WebhookLink][yuyo.links.WebhookLink] handles parsing webhook links.

This class inherits from [hikari.ExecutableWebhook][hikari.webhooks.ExecutableWebhook] and
therefore has all the webhook execute methods you'll find on interaction and webhook objects.

```py
--8<-- "./docs_src/links.py:92:93"
```

[links.make_webhook_link][yuyo.links.make_webhook_link] offers an alternative
way to make a webhook link string which doesn't require having a Bot or REST
app in scope.
