# List Status

[yuyo.list_status][] provides an easy way to update a Bot's stats on bot lists.

By default this will track the count per-shard, meaning that this'll have to be
running on each shard cluster instance to properly keep track of the count.
This will also be relying on the GUILDS intent being declared unless a custom
counting strategy is passed.

### Usage

```py
--8<-- "./docs_src/list_status.py:24:25"
```

[TopGGService][yuyo.list_status.TopGGService] is used to set <https://top.gg>
as one of the targets for updating the bot's guild count.

Top.GG API tokens are found in the "webhooks" tab while editing the bot's entry.

```py
--8<-- "./docs_src/list_status.py:29:30"
```

[DiscordBotListService][yuyo.list_status.DiscordBotListService] is used to set
<https://discordbotlist.com> as one of the targets for updating the bot's guild
count.

<!-- TODO: where to find token? -->

```py
--8<-- "./docs_src/list_status.py:34:35"
```

[BotsGGService][yuyo.list_status.BotsGGService] is used to set
<https://discord.bots.gg> as one of the targets for updating the bot's guild
count.

Bots.gg API tokens are found at <https://discord.bots.gg/docs> (when logged in).

##### Custom service

```py
--8<-- "./docs_src/list_status.py:45:56"
```

Services are simply asynchronous callbacks which call
`AbstractManager.counter.count` to get the most recent count(s) then pass it on.

`AbstractManager.counter.count` may raise [CountUnknownError][yuyo.list_status.CountUnknownError]
to indicate an unknown state and will return either [int][] to indicate a
global guild count or `Mapping[int, int]` to give per-shard guild counts.

### Counting Strategies

##### Sake counting

```py
--8<-- "./docs_src/list_status.py:39:41"
```

The Sake strategy lets this be used with an asynchronous Redis guild cache.
This strategy will only be keeping track of a global guild count (rather than
per-shard like the default counters) and therefore you should only ever need to
have one instance of this running with Sake.
