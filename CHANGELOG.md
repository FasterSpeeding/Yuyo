# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
## [1.7.0a1] - 2023-02-14
### Added
- Support for the new select menu types to `yuyo.to_builder`.
- [ActionRowExecutor.add_channel_select][yuyo.components.ActionRowExecutor.add_channel_select]
  for adding channel select menus to an action row.
- [ActionRowExecutor.add_select_menu][yuyo.components.ActionRowExecutor.add_select_menu] for
  adding the other new select menu types to an action row.
- [yuyo.pagination.Page][] type which can be used to represent a response page in the paginators.
  This allows configuring attachments and multiple embeds for a page.
- Methods for manually setting the buttons for [yuyo.components.ComponentPaginator][] and
  [yuyo.reactions.ReactionPaginator][] which allow manually overriding the config for each button
  or reaction.

### Changed
- `from_gateway_bot` classmethods can now also take cache-less `ShardAware` bots.
- Bumped minimum Hikari version to `2.0.0.dev116`.
- Renamed `ErrorManager.with_rule` to [ErrorManager.add_rule][yuyo.backoff.ErrorManager.add_rule]
  and made its arguments positional only.
- The `guild` argument for [yuyo.chunk_tracker.ChunkTracker.request_guild_members][] is now
  positional only.
- `iterator` is now positional only in
  [ReactionPaginator.\_\_init\_\_][yuyo.reactions.ReactionPaginator.__init__] and
  [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__].
- `lines` is now positional only in [yuyo.pagination.async_paginate_string][],
  [yuyo.pagination.sync_paginate_string][] and [yuyo.pagination.paginate_string][].
- Renamed `add_callback` to `set_callback` on `ComponentExecutor` and `ReactionHandler`.
- [ActionRowExecutor.add_button][yuyo.components.ActionRowExecutor.add_button] now takes all
  the button's options as arguments.
  This also now returns the action row and adds the button to the row immediately (without
  any calls to `add_to_parent`).
- Renamed the old `ActionRowExecutor.add_select_menu` to
  [ActionRowExecutor.add_text_select][yuyo.components.ActionRowExecutor.add_text_select]
  and added the other select menu's config as keyword-arguments.
- Renamed `add_handler` to [ReactionClient.set_handler][yuyo.reactions.ReactionClient.set_handler].
- [ReactionClient.set_handler][yuyo.reactions.ReactionClient.set_handler]'s arguments are now all
  positional-only.
- [ComponentPaginator.get_next_entry][yuyo.components.ComponentPaginator.get_next_entry] and
  [ReactionPaginator.get_next_entry][yuyo.reactions.ReactionPaginator.get_next_entry] now both
  return [yuyo.pagination.Page][] rather than a tuple.
  This can be used to create a response easily by passing the result of
  [Page.to_kwargs][yuyo.pagination.Page.to_kwargs] to the create message or execute webhook REST method as `**kwargs`.

### Fixed
- `Context.create_initial_response` (and by extension `Context.respond` for the initial
  response specifically) will no-longer try to pass the attachment, component or embed as
  the actual message content when passed for the `content` argument for REST-based
  interaction commands.
- `BLACK_CROSS` can now be passed to
  [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__] and
  [ReactionPaginator.\_\_init\_\_][yuyo.reactions.ReactionPaginator.__init__]
  in the `triggers` array to enable the stop button.
- The configured executor is now used for handling attachments when creating the initial responses
  with the ASGI bot.
- Check the headers before reading the body in the ASGI adapter and bot to avoid unnecessary hold up
  on bad requests.

### Removed
- `yuyo.InteractiveButtonBuilder`/`yuyo.components.InteractiveButtonBuilder` and
  `yuyo.SelectMenuBuilder`/`yuyo.components.SelectMenuBuilder`. Hikari's default
  implementations should be used instead.
- The deprecated `load_from_attributes` arguments and the relevant deprecated `as_reaction_callback`
  and `as_component_callback` functions.
- The deprecated `WaitForComponent` alias of `WaitForExecutor`.

### Security
- The [yuyo.asgi.AsgiAdapter][] and [yuyo.asgi.AsgiBot][] both now have a max body size limit to avoid
  potential DoS and memory issues. This is configurable using `max_body_size` in the `__init__`s.

## [1.6.1a1] - 2023-01-17
### Changed
- Detect/allow invite links which aren't prefixed by `https://` or `https://www.` in
  [InviteLink.find][yuyo.links.BaseLink.find],
  [InviteLink.find_iter][yuyo.links.BaseLink.find_iter], and
  [InviteLink.from_link][yuyo.links.BaseLink.from_link] to better match Discord's special invite
  embedding logic.
- All link parsers now allow `http://` links.
- The startup and shutdown callbacks on [yuyo.asgi.AsgiAdapter][] now take no arguments.
  This change does **not** effect startup and shutdown callbacks on [yuyo.asgi.AsgiBot][].

### Removed
- The `process_lifespan_event` and `process_request` methods from [yuyo.asgi.AsgiAdapter][].
- [yuyo.asgi.AsgiBot][] no-longer inherits from [yuyo.asgi.AsgiAdapter][] directly but still
  functions as one.

## [1.6.0a1] - 2023-01-12
### Added
- Helper functions for converting some Hikrai models to builder objects in [yuyo.to_builder][].
  These support application commands and message components.

### Changed
- Bumped minimum Hikari version to `v2.0.0.dev114`.

## [1.5.0a1] - 2023-01-10
### Added
- Add classes and functions for handling message, webhook, invite and template links.

### Changed
- Officially drop support for Python 3.8.

## [1.4.0a1.post1] - 2022-11-20
### Changed
- [CacheStrategy.\_\_init\_\_][yuyo.list_status.CacheStrategy.__init__] now
  takes two arguments `(hikari.api.Cache, hikari.ShardAware)`.

### Fixed
- [yuyo.list_status.DiscordBotListService][]'s logging when declaring per-shard stats.
- Declare bot stats per-shard instead of for the whole bot when list status is using the
  standard cache or event strategies.

## [1.4.0a1] - 2022-11-20
### Added
- A system for automatically declaring a bot's guild count on the bot lists
  top.gg, bots.gg and discordbotlist.com. See [yuyo.list_status][] for more
  information.
- `"asgi"` feature flag for ensuring this installs with the dependencies required to run
  the Asgi REST bot adapter.

### Changed
- [yuyo.backoff.Backoff][] now increments the internal counter regardless of whether
  [yuyo.backoff.Backoff.set_next_backoff][] has been called.
- [yuyo.backoff.Backoff][] now iterates over the retry counter ([int][]), starting at 0,
  rather than just [None][].
- [yuyo.backoff.Backoff.backoff][] now returns the current retry count as [int][] or
  [None][] if it has reached max retries or the finished flag has been set.
- Allow [None][] to be passed for `attachment` and `attachments` to edit response methods.
- Star imports are no-longer used on the top level (at [yuyo][]) so only the attributes present
  in `yuyo.__all__` can be accessed there now.
- [yuyo.components.AbstractComponentExecutor][], [yuyo.components.ChildActionRowExecutor][],
  `InteractiveButtonBuilder`, `yuyo.components.as_child_executor`,
  `yuyo.components.as_component_callback`, [yuyo.reactions.AbstractReactionHandler][], and
  `yuyo.reactions.as_reaction_callback` are no longer included in `yuyo.__all__`/exported
  top-level.

### Deprecated
- `yuyo.components.as_child_executor`, `yuyo.components.as_component_callback`, and
  `yuyo.components.as_reaction_callback` are no longer documented (included in their
  relevant module's `__all__`) as these are considered deprecated and undocumented.

### Fixed
- [yuyo.backoff.Backoff.backoff][] now respects the max retires config and finished flag.
  For this it will now return [None][] without sleeping when either has been reached.

### Removed
- `backoff` option from [yuyo.backoff.Backoff.backoff][] to better match the aiter flow.

## [1.3.1a1] - 2022-11-07
### Added
- A chunk request tracker implementation.

### Changed
- Bumped the minimum Hikari version to `2.0.0.dev112`.
- [yuyo.asgi.AsgiAdapter][]'s startup and shutdown callbacks now take 1 argument,
  must return [None][] and must be asynchronous to match the methods added to
  [hikari.traits.RESTBotAware][] in
  <https://github.com/hikari-py/hikari/releases/tag/2.0.0.dev112>.

  This argument will be of type [yuyo.asgi.AsgiAdapter][] when these methods are
  called of an asgi adapter and of type [yuyo.asgi.AsgiBot][] when called on an
  asgi bot instance.

### Removed
- `replace_attachments` argument from the relevant context edit response methods.
  For more information see <https://github.com/hikari-py/hikari/releases/tag/2.0.0.dev112>.

## [1.2.1a1] - 2022-11-04
### Added
- `ephemeral` keyword-argument to [yuyo.components.ComponentContext][]'s `create_initial_response`,
  `create_follow_up` and `defer` methods as a shorthand for including `1 << 6` in the passed flags.
- `delete_after` option to [yuyo.components.ComponentContext][] response methods.
- `expires_at` property to [yuyo.components.ComponentContext][].
- Support for dependency injection through [Alluka][alluka] to the reaction and component clients.

### Changed
- `ComponentExecutor.execute` now takes a context object instead of interaction and future objects.
- [yuyo.pagination.async_paginate_string][], [yuyo.pagination.sync_paginate_string][] and
  [yuyo.pagination.paginate_string][] now return an (async) iterator of the [str][] pages rather than
  an iterator of `tuple[str, int]`. If you need page counts, use [enumerate][] or
  [yuyo.pagination.aenumerate][].
- (Async) iterables can now be passed to [yuyo.pagination.async_paginate_string][],
  [yuyo.pagination.sync_paginate_string][] and [yuyo.pagination.paginate_string][] instead of just
  iterators.

### Fixed
- [yuyo.components.ComponentContext.respond][] trying to edit in the initial response instead
  of create a follow up if a deferred initial response was deleted.
- Long running `delete_after` and component execution tasks will no-longer be cancelled by GC.

### Removed
- The project metadata dunder attributes from [yuyo][].
  [importlib.metadata][] should be used to get this metadata instead.

## [1.1.1a1] - 2022-08-28
### Added
- Support for sending attachments in the initial response to the ASGI server implementation.
- Support for sending attachments on initial response to the `ComponentContext`.

### Changed
- Bumped the minimum hikari version to dev109.
- Async functions must be typed as returning `typing.Coroutine`/`collections.abc.Coroutine`
  rather than `typing.Awaitable` now.

### Fixed
- Several bug fixes on handling context response tracking have been copied over from Tanjun
  to `ComponentContext`.

## [1.0.6a1] - 2022-05-24
### Changed
- Bumped the minimum hikari version to dev108.

### Fixed
- `WaitForExecutor` now has better semantics/behaviour around being called when it's inactive.
  Timeouts are now handled better meaning that a wait for executor timeout will mark it to be
  de-registered.
  Execute calls to an executor that hasn't been waited for yet will

## [1.0.5a1.post1] - 2021-12-21
### Changed
- `AsgiBot` is now (by default) started and closed based on the ASGI lifespan events with
  the `asgi_managed` keyword argument to `AsgiBot.__init__` allowing this to be disabled.

## [1.0.5a1] - 2021-12-21
### Added
- `AsgiBot` extension for `AsgiAdapter` which can be run by itself (manages a rest client).

### Changed
- Renamed `WaitForComponent` to `WaitForExecutor`.

## [1.0.4a1] - 2021-11-22
### Added
- `prefix_match` option to ComponentClient custom ids to make storing metadata in custom ids
  possible.

### Fixed
- custom id methods now raise ValueError on conflict rather than KeyError.

## [1.0.3a1] - 2021-10-27
### Added
- An ASGI/3 adapter for Hikari's interaction server.
- Ability to register a callback for a constant custom_id in the component client.
  This takes precedence over any registered component executors.

### Changed
- Renamed `components.WaitFor` to `WaitForComponent` and added it to `components.__all__` and
  `yuyo.__all__`.

### Fixed
- `Context.defer` is now used in the ComponentPaginator instead of
  `Context.create_initial_response` to defer the initial response since before deleting it
  as `Context.create_initial_response` errors in the REST flow when a defer type is passed.
- `Context.create_initial_response` is no longer typed as taking deferred types.
- Handling of authors in WaitForComponent.
- Added timeout handling to the future returned by WaitForComponent.wait_for.


## [1.0.2a1.post1] - 2021-10-02
### Fixed
- ComponentClient erroneously garbage collecting unexpired executors.
- ComponentPaginator and ReactionPaginator both starting on index 1 instead of 0.


## [1.0.2a1] - 2021-10-02
### Added
- Option to have the ComponentClient be event managed when linked to an event manager.
  This is True by default.

### Changed
- The client now gives a ephemeral timed out response when an unknown message is received.

### Fixed
- ComponentClient's gc task not being started when its opened.
- Handling of access errors in the component client.
- MultiComponentExecutor slots.

## [1.0.1a1] - 2021-09-21
### Added
- Higher level component execution client and a pagination specific implementation of its
  executor.

### Changed
- Totally refactored reaction pagination client to make it more abstract and abstracted away from
  pagination where the pagination is just a standard use case specific implementation of its
  executor.
- Renamed module pagnation to pagination.
- Move the reaction handling logic over to "reactions.py"
- Renamed string_patinator functions to paginate_string

### Fixed
- Iffy behaviour around "locking" the reaction executor which lead to some requests just being ignored.

[Unreleased]: https://github.com/FasterSpeeding/Yuyo/compare/v1.7.0a1...HEAD
[1.7.0a1]:https://github.com/FasterSpeeding/Yuyo/compare/v1.6.1a1...v1.7.0a1
[1.6.1a1]:https://github.com/FasterSpeeding/Yuyo/compare/v1.6.0a1...v1.6.1a1
[1.6.0a1]:https://github.com/FasterSpeeding/Yuyo/compare/v1.5.0a1...v1.6.0a1
[1.5.0a1]:https://github.com/FasterSpeeding/Yuyo/compare/v1.4.0a1.post1...v1.5.0a1
[1.4.0a1.post1]:https://github.com/FasterSpeeding/Yuyo/compare/v1.4.0a1...v1.4.0a1.post1
[1.4.0a1]:https://github.com/FasterSpeeding/Yuyo/compare/v1.3.1a1...v1.4.0a1
[1.3.1a1]:https://github.com/FasterSpeeding/Yuyo/compare/v1.2.1a1...v1.3.1a1
[1.2.1a1]:https://github.com/FasterSpeeding/Yuyo/compare/v1.0.6a1...v1.2.1a1
[1.1.1a1]:https://github.com/FasterSpeeding/Yuyo/compare/v1.0.6a1...v1.1.1a1
[1.0.6a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.5a1.post1...v1.0.6a1
[1.0.5a1.post1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.5a1...v1.0.5a1.post1
[1.0.5a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.4a1...v1.0.5a1
[1.0.4a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.3a1...v1.0.4a1
[1.0.3a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.2a1...v1.0.3a1
[1.0.2a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.1a1...v1.0.2a1
[1.0.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/0.0.2...v1.0.1a1
