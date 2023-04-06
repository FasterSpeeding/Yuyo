# Chunk Tracker

The chunk tracker in [yuyo.chunk_tracker][] dispatches custom chunk request
tracking events. This can be a useful way to work out when the cache will be
reliable for a guild or globally (when combined with checking the intent and
cache config).

```py
--8<-- "./docs_src/chunk_tracker.py:22:22"
```

While this is easy to setup, there are some things you need to account for.
This will only track chunk requests (including startup chunk requests) as long
if have a set nonce (luckily Hikari's startup requests include nonces).
[ChunkTracker.request_guild_members][yuyo.chunk_tracker.ChunkTracker.request_guild_members]
ensures that a nonce is always set.

The chunk tracker can be configured to automatically send chunk requests (with
nonces) on guild join itself using
[ChunkTracker.set_auto_chunk_members][yuyo.chunk_tracker.ChunkTracker.set_auto_chunk_members].
This can be useful if you need auto chunking in scenarios where it
otherwise would be disabled (e.g. when using a separate async cache instead of
Hikari's builtin cache).

### Events

##### Chunk Request Finished Event

[ChunkRequestFinishedEvent][yuyo.chunk_tracker.ChunkRequestFinishedEvent] is
dispatched when a specific chunk request has finished.

```py
--8<-- "./docs_src/chunk_tracker.py:26:35"
```

This is only dispatch for chunk requests where a `nonce` has been set.

##### Finished Chunking Event

[FinishedChunkingEvent][yuyo.chunk_tracker.FinishedChunkingEvent] is dispatched
when the startup chunking has finished for the bot to indicate that the member
and presence caches should be complete (if enabled).

```py
--8<-- "./docs_src/chunk_tracker.py:39:41"
```

This is only dispatched once per-bot lifetime.

##### Shard Finished Chunking Event

[ShardFinishedChunkingEvent][yuyo.chunk_tracker.ShardFinishedChunkingEvent] is
dispatched when the startup chunking has finished for a specific shard to
indicate that the member and presence caches should be complete for the guilds
covered by this shard.

```py
--8<-- "./docs_src/chunk_tracker.py:45:50"
```
