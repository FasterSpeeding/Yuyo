# Links

Yuyo provides some utilities for handling Discord links in [yuyo.links][].

### BaseLink

All [BaseLink][yuyo.links.BaseLink] implementations come with 3
classmethods for parsing them from strings.

All of these methods take a Hikari "app" (Bot or REST app object) as their
first argument.

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

There are 5 implementations of [BaseLink][yuyo.links.BaseLink] provided by
Yuyo (which all support the parsing methods listed above):

##### Channel links

```py
--8<-- "./docs_src/links.py:34:43"
```

[ChannelLink][yuyo.links.ChannelLink] handles parsing channel links.

[ChannelLink.guild_id][yuyo.links.ChannelLink.guild_id] will be [None][] for
DM channels.

```py
--8<-- "./docs_src/links.py:47:50"
```

[links.make_channel_link][yuyo.links.make_channel_link] lets you make a channel
link string.

##### Invite links

```py
--8<-- "./docs_src/links.py:54:59"
```

[InviteLink][yuyo.links.InviteLink] handles parsing invite links.

```py
--8<-- "./docs_src/links.py:63:64"
```

[links.make_invite_link][yuyo.links.make_invite_link] lets you make an invite
link string.

##### Message links

```py
--8<-- "./docs_src/links.py:68:80"
```

[MessageLink][yuyo.links.MessageLink] handles parsing message links.

[MessageLink.guild_id][yuyo.links.ChannelLink.guild_id] will be [None][] for
DM messages.

```py
--8<-- "./docs_src/links.py:84:88"
```

[links.make_message_link][yuyo.links.make_message_link] lets you make a message
link string.

##### Guild template links

```py
--8<-- "./docs_src/links.py:92:96"
```

[TemplateLink][yuyo.links.TemplateLink] handles parsing guild template links.

```py
--8<-- "./docs_src/links.py:100:101"
```

[links.make_template_link][yuyo.links.make_template_link] lets you make a
template link string.

##### Webhook links

```py
--8<-- "./docs_src/links.py:105:110"
```

[WebhookLink][yuyo.links.WebhookLink] handles parsing webhook links.

This class inherits from [hikari.ExecutableWebhook][hikari.webhooks.ExecutableWebhook] and
therefore has all the webhook execute methods you'll find on interaction and webhook objects.

```py
--8<-- "./docs_src/links.py:114:115"
```

[links.make_webhook_link][yuyo.links.make_webhook_link] lets you make a webhook
link string.


### Bot invite links

```py
--8<-- "./docs_src/links.py:119:121"
```

[links.make_bot_invite][yuyo.links.make_bot_invite] lets you make a bot invite link.

This takes the bot's ID as its first argument and has several optional parameters:

- `permissions`: Specifies the permissions to request.
- `guild`: ID of a specific guild to pre-select for the user.
- `disable_guild_select`: Whether to stop the user from selecting another guild when
  `guild` has also been passed.

[links.make_oauth_link][yuyo.links.make_oauth_link] can also be used to
make more general Oauth2 authorize links.
