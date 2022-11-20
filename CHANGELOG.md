# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
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

[Unreleased]: https://github.com/FasterSpeeding/Yuyo/compare/v1.4.0a1...HEAD
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
