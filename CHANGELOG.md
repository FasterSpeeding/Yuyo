# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/olivierlacan/keep-a-changelog/compare/v1.0.2a1...HEAD
[1.0.2a1]: https://github.com/olivierlacan/keep-a-changelog/compare/v1.0.1a1...v1.0.2a1
[1.0.1a1]: https://github.com/olivierlacan/keep-a-changelog/compare/0.0.2...v1.0.1a1
