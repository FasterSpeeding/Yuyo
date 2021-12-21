# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.5a1.post1...HEAD
[1.0.5a1.post1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.5a1...v1.0.5a1.post1
[1.0.5a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.4a1...v1.0.5a1
[1.0.4a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.3a1...v1.0.4a1
[1.0.3a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.2a1...v1.0.3a1
[1.0.2a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.1a1...v1.0.2a1
[1.0.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/0.0.2...v1.0.1a1
