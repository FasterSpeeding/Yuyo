# Chunk Tracker


### Events

##### ChunkRequestFinishedEvent

[ChunkRequestFinishedEvent][yuyo.chunk_tracker.ChunkRequestFinishedEvent] is
dispatched when a specific chunk request has finished.

This is only dispatch for chunk requests where a `none` has been set.

##### FinishedChunkingEvent

[FinishedChunkingEvent][yuyo.chunk_tracker.FinishedChunkingEvent] is dispatched
when the startup chunking has finished for the bot to indicate that the member
and presence caches should be complete (if enabled).

This is only dispatched once per-bot lifetime.

##### ShardFinishedChunkingEvent

[ShardFinishedChunkingEvent][yuyo.chunk_tracker.ShardFinishedChunkingEvent] is
dispatched when the startup chunking has finished for a specific shard to
indicate that the member and presence caches should be complete for the guilds
covered by this shard.
