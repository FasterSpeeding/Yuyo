# Yuyo

A collection of utility classes and functions designed to expand Hikari.

# Instillation

You can install yuyo from PyPI using the following command.

```
python -m pip install -U hikari-yuyo
```

The following feature flags ensure feature-specific optional dependencies are also installed:

* `hikari-yuyo[asgi]` ensures the dependencies required to run the Asgi RESTBot adapter.
* `hikari-yuyo[cli]` ensures the dependencies required to use the provided CLI commands are
  installed.
* `hikari-yuyo[sake]` can be used to ensure the installed Sake version is compatible with
  Yuyo's functionality which uses Sake. You should still have a Sake version pinned in your
  own requirements as this just provides an accepted range for the dependency.
* `hikari-yuyo[tanjun]` can be used to ensure the installed Tanjun version is compatible with
  Yuyo's Tanjun support (i.e. the `from_tanjun`) class methods.

# Quick Usage.

For usage see the the [documentation](https://yuyo.cursed.solutions/) and, more
specifically, the [usage guide](https://yuyo.cursed.solutions/usage/).

# Support

Go to the [support server](https://discord.gg/bZ7BrYJ63g) for support.

# Contributing

Before contributing you should read through the
[contributing guidelines](https://github.com/FasterSpeeding/Yuyo/blob/master/CONTRIBUTING.md) and
the [code of conduct](https://github.com/FasterSpeeding/Yuyo/blob/master/CODE_OF_CONDUCT.md).
