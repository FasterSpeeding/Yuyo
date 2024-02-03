# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Copyright (c) 2023, Faster Speeding
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""Functions used to persist command metadata (i.e. permissions) while renaming them."""
from __future__ import annotations

__all__: list[str] = []

import asyncio
import dataclasses
import enum
import json
import logging
import pathlib
import sys
import typing
import unicodedata

import click
import dotenv
import hikari
import pydantic
import pydantic.functional_validators
import pydantic_core

from yuyo import to_builder

if typing.TYPE_CHECKING:
    from collections import abc as collections

    from typing_extensions import Self


if sys.version_info >= (3, 11):
    import tomllib

    def _parse_toml(data: typing.BinaryIO) -> typing.Any:
        return tomllib.load(data)

else:
    import tomli

    def _parse_toml(data: typing.BinaryIO) -> typing.Any:
        return tomli.load(data)


_EnumT = typing.TypeVar("_EnumT", bound=enum.Enum)
_CONFIG_PARSERS: dict[str, collections.Callable[[typing.BinaryIO], typing.Any]] = {
    "json": json.load,
    "toml": _parse_toml,
    # TODO: yaml?
}


def _parse_config(path: pathlib.Path) -> typing.Any:
    file_type = path.name.rsplit(".", 1)[-1]
    try:
        return _CONFIG_PARSERS[file_type]

    except KeyError:
        logging.exception(f"Unknown file type {file_type}")
        exit(1)


@click.group(name="tanjun")
def _cli() -> None:
    dotenv.load_dotenv()


_CommandTypes = typing.Literal["message_menu", "slash", "user_menu"]
_COMMAND_TYPES: dict[hikari.CommandType, _CommandTypes] = {
    hikari.CommandType.MESSAGE: "message_menu",
    hikari.CommandType.SLASH: "slash",
    hikari.CommandType.USER: "user_menu",
}

_LOGGER = logging.getLogger("hikari.yuyo")


@dataclasses.dataclass
class _MaybeLocalised:
    field_name: str
    value: str
    localisations: collections.Mapping[str, str]

    @classmethod
    def parse(cls, field_name: str, raw_value: typing.Union[str, collections.Mapping[_Locale, str]], /) -> Self:
        if isinstance(raw_value, str):
            return cls(field_name=field_name, value=raw_value, localisations={})

        else:
            value = raw_value.get("default") or next(iter(raw_value))
            localisations: dict[str, str] = {k: v for k, v in raw_value.items() if k != "default"}
            return cls(field_name=field_name, value=value, localisations=localisations)

    def _values(self) -> collections.Iterable[str]:
        yield self.value
        yield from self.localisations.values()

    def assert_matches(
        self, pattern: str, match: collections.Callable[[str], bool], /, *, lower_only: bool = False
    ) -> Self:
        for value in self._values():
            if not match(value):
                raise ValueError(
                    f"Invalid {self.field_name} provided, {value!r} doesn't match the required regex `{pattern}`"
                )

            if lower_only and value.lower() != value:
                raise ValueError(f"Invalid {self.field_name} provided, {value!r} must be lowercase")

        return self

    def assert_length(self, min_length: int, max_length: int, /) -> Self:
        lengths = sorted(map(len, self._values()))
        real_min_len = lengths[0]
        real_max_len = lengths[-1]

        if real_max_len > max_length:
            raise ValueError(
                f"{self.field_name.capitalize()} must be less than or equal to {max_length} characters in length"
            )

        if real_min_len < min_length:
            raise ValueError(
                f"{self.field_name.capitalize()} must be greater than or equal to {min_length} characters in length"
            )

        return self


def _cast_snowflake(value: int) -> hikari.Snowflake:
    if hikari.Snowflake.min() <= value <= hikari.Snowflake.max():
        return hikari.Snowflake(value)

    raise ValueError(f"{value} is not a valid snowflake")


class _SnowflakeSchema:
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: type[typing.Any], _handler: pydantic.GetCoreSchemaHandler
    ) -> pydantic_core.CoreSchema:
        from_schema = pydantic_core.core_schema.chain_schema(
            [
                pydantic_core.core_schema.int_schema(),
                pydantic_core.core_schema.no_info_plain_validator_function(_cast_snowflake),
            ]
        )
        return pydantic_core.core_schema.json_or_python_schema(
            json_schema=from_schema,
            python_schema=pydantic_core.core_schema.union_schema(
                [pydantic_core.core_schema.is_instance_schema(hikari.Snowflake), from_schema]
            ),
        )


_Snowflake = typing.Annotated[hikari.Snowflake, _SnowflakeSchema]


class _EnumSchema:
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[_EnumT], _handler: pydantic.GetCoreSchemaHandler
    ) -> pydantic_core.CoreSchema:
        def _cast_enum(value: typing.Union[str, int]) -> _EnumT:
            result = source_type(value)
            if isinstance(result, source_type):
                return result

            raise ValueError(f"{value!r} is not a valid {source_type.__name__}")

        if issubclass(source_type, int):
            origin_schema = pydantic_core.core_schema.int_schema()

        elif issubclass(source_type, str):
            origin_schema = pydantic_core.core_schema.str_schema()

        else:
            raise NotImplementedError("Only string and int schemas are supported")

        from_schema = pydantic_core.core_schema.chain_schema(
            [origin_schema, pydantic_core.core_schema.no_info_plain_validator_function(_cast_enum)]
        )
        return pydantic_core.core_schema.json_or_python_schema(
            json_schema=from_schema,
            python_schema=pydantic_core.core_schema.union_schema(
                [pydantic_core.core_schema.is_instance_schema(source_type), from_schema]
            ),
        )


_LocaleSchema = typing.Annotated[hikari.Locale, _EnumSchema]
_Locale = typing.Union[typing.Literal["default"], _LocaleSchema]
_MaybeLocalisedType = typing.Union[str, dict[_Locale, str]]


class _RenameModel(pydantic.BaseModel):
    commands: dict[typing.Union[str, _Snowflake], typing.Union[str, dict[_Locale, str]]]


async def _rename_coro(
    token: str,
    renames: collections.Mapping[
        typing.Union[str, hikari.Snowflake], typing.Union[str, collections.Mapping[_Locale, str]]
    ],
) -> None:
    app = hikari.RESTApp()
    new_commands: list[hikari.api.CommandBuilder] = []
    renames = dict(renames)

    if not renames:
        raise RuntimeError("No commands passed")

    # TODO: allow doing this all in one async with statement.
    # TODO: support using bearer tokens.
    # TODO: support guild specific commands.
    await app.start()

    async with app.acquire(token) as rest:
        application = await rest.fetch_application()
        commands = await rest.fetch_application_commands(application)

        for command in commands:
            new_name = (
                renames.pop(command.id, None)
                or renames.pop(f"{_COMMAND_TYPES[command.type]}:{command.name}")
                or renames.pop(command.name, None)
            )
            builder = to_builder.to_cmd_builder(command)

            if new_name:
                names = _MaybeLocalised.parse("name", new_name).assert_length(1, 32)
                if command.type is hikari.CommandType.SLASH:
                    names.assert_matches(_SCOMMAND_NAME_REG, _validate_slash_name)

                builder.set_name(names.value)
                builder.set_name_localizations(names.localisations)

            new_commands.append(builder)

        if renames:
            if _LOGGER.isEnabledFor(logging.CRITICAL):
                _LOGGER.critical("Couldn't find the following commands:\n" + "\n".join(f"- {name}" for name in renames))
            exit(1)

        await rest.set_application_commands(application, new_commands)


@click.option("--file", "-f", type=click.Path(exists=True, path_type=pathlib.Path))
@click.option(
    "--token", envvar="DISCORD_TOKEN", help="Discord token for the bot to rename the commands for.", required=True
)
@_cli.command(name="rename")
def _rename(token: str, file: typing.Optional[pathlib.Path]) -> None:  # pyright: ignore[reportUnusedFunction]
    """"""
    if file is not None:
        commands = _RenameModel.model_validate(_parse_config(file), strict=True).commands

    else:
        raise NotImplementedError

    asyncio.run(_rename_coro(token, commands))


class _CommandModel(pydantic.BaseModel):
    ...

    def to_builder(self) -> hikari.api.CommandBuilder:
        raise NotImplementedError


class _CommandChoiceModel(pydantic.BaseModel):
    """Represents the choices set for an application command's argument."""

    name: _MaybeLocalisedType
    value: typing.Union[str, int, float]

    def to_choice(self) -> hikari.CommandChoice:
        # TODO: regex
        name = _MaybeLocalised.parse("name", self.name).assert_length(1, 32)
        return hikari.CommandChoice(name=name.value, name_localizations=name.localisations, value=self.value)


_OptionType = typing.Annotated[hikari.OptionType, _EnumSchema]
_ChannelType = typing.Annotated[hikari.ChannelType, _EnumSchema]


class _CommandOptionModel(pydantic.BaseModel):
    type: _OptionType
    name: _MaybeLocalisedType
    description: _MaybeLocalisedType
    is_required: bool = False
    choices: list[_CommandChoiceModel] = pydantic.Field(default_factory=list)
    options: list[_CommandOptionModel] = pydantic.Field(default_factory=list)
    channel_types: list[_ChannelType] = pydantic.Field(default_factory=list)
    autocomplete: bool = False
    min_value: typing.Union[int, float, None] = None
    max_value: typing.Union[int, float, None] = None
    min_length: typing.Optional[int] = None
    max_length: typing.Optional[int] = None

    def to_option(self) -> hikari.CommandOption:
        # TODO: regex
        name = _MaybeLocalised.parse("name", self.name).assert_length(1, 32)
        description = _MaybeLocalised.parse("description", self.description).assert_length(1, 100)
        return hikari.CommandOption(
            type=self.type,
            name=name.value,
            description=description.value,
            choices=[choice.to_choice() for choice in self.choices],
            options=[opt.to_option() for opt in self.options],
            channel_types=self.channel_types,
            autocomplete=self.autocomplete,
            min_value=self.min_value,
            max_value=self.max_value,
            name_localizations=name.localisations,
            description_localizations=description.localisations,
            min_length=self.min_length,
            max_length=self.max_length,
        )


_SCOMMAND_NAME_REG: typing.Final[str] = r"^[-_\p{L}\p{N}\p{sc=Deva}\p{sc=Thai}]{1,32}$"
_VALID_NAME_UNICODE_CATEGORIES = frozenset(
    (
        # L
        "Lu",
        "Ll",
        "Lt",
        "Lm",
        "Lo",
        # N
        "Nd",
        "Nl",
        "No",
    )
)
_VALID_NAME_CHARACTERS = frozenset(("-", "_"))


def _check_name_char(character: str, /) -> bool:
    # `^[-_\p{L}\p{N}\p{sc=Deva}\p{sc=Thai}]{1,32}$`
    # * `-_`` is just `-` and `_`
    # * L (all letter characters so "Lu", "Ll", "Lt", "Lm" and "Lo")
    # * N (all numeric characters so "Nd", "Nl" and "No")
    # * Deva: `\u0900-\u097F`  # TODO: Deva extended?
    # * Thai: `\u0E00-\u0E7F`

    return (
        character in _VALID_NAME_CHARACTERS
        or unicodedata.category(character) in _VALID_NAME_UNICODE_CATEGORIES
        or 0x0900 >= (code_point := ord(character)) <= 0x097F
        or 0x0E00 >= code_point <= 0x0E7F
    )


def _validate_slash_name(name: str, /) -> bool:
    return all(map(_check_name_char, name))


class _DeclareSlashCmdModel(_CommandModel):
    type: typing.Literal[hikari.CommandType.SLASH] = hikari.CommandType.SLASH
    name: _MaybeLocalisedType
    description: _MaybeLocalisedType
    id: typing.Optional[_Snowflake] = None
    default_member_permissions: typing.Optional[int] = None
    is_dm_enabled: bool = True
    is_nsfw: bool = False
    options: list[_CommandOptionModel] = pydantic.Field(default_factory=list)

    def to_builder(self) -> hikari.api.SlashCommandBuilder:
        default_member_permissions = hikari.UNDEFINED
        if self.default_member_permissions is not None:
            default_member_permissions = self.default_member_permissions

        name = (
            _MaybeLocalised.parse("name", self.name)
            .assert_length(1, 32)
            .assert_matches(_SCOMMAND_NAME_REG, _validate_slash_name)
        )
        description = _MaybeLocalised.parse("description", self.description).assert_length(1, 100)
        return hikari.impl.SlashCommandBuilder(
            name=name.value,
            description=description.value,
            id=hikari.UNDEFINED if self.id is None else hikari.Snowflake(self.id),
            default_member_permissions=default_member_permissions,
            is_dm_enabled=self.is_dm_enabled,
            is_nsfw=self.is_nsfw,
            name_localizations=name.localisations,
            options=[opt.to_option() for opt in self.options],
            description_localizations=description.localisations,
        )


class _DeclareMenuCmdModel(_CommandModel):
    type: typing.Union[typing.Literal[hikari.CommandType.MESSAGE], typing.Literal[hikari.CommandType.USER]]
    name: _MaybeLocalisedType
    id: typing.Optional[_Snowflake] = None
    default_member_permissions: typing.Optional[int] = None
    is_dm_enabled: bool = True
    is_nsfw: bool = False

    def to_builder(self) -> hikari.api.ContextMenuCommandBuilder:
        default_member_permissions = hikari.UNDEFINED
        if self.default_member_permissions is not None:
            default_member_permissions = self.default_member_permissions

        name = _MaybeLocalised.parse("name", self.name).assert_length(1, 31)
        return hikari.impl.ContextMenuCommandBuilder(
            type=self.type,
            name=name.value,
            id=hikari.UNDEFINED if self.id is None else hikari.Snowflake(self.id),
            default_member_permissions=default_member_permissions,
            is_dm_enabled=self.is_dm_enabled,
            is_nsfw=self.is_nsfw,
            name_localizations=name.localisations,
        )


class _DeclareModel(pydantic.BaseModel):
    commands: list[typing.Union[_DeclareSlashCmdModel, _DeclareMenuCmdModel]]


async def _declare_coro(token: str, schema: _DeclareModel) -> None:
    app = hikari.RESTApp()
    await app.start()

    async with app.acquire(token) as rest:
        application = await rest.fetch_application()
        await rest.set_application_commands(application.id, [cmd.to_builder() for cmd in schema.commands])


@click.option(
    "--schema",
    "-s",
    default="bot.schema",
    envvar="BOT_SCHEMA_FILE",
    help="",
    type=click.Path(exists=True, path_type=pathlib.Path),
)
@click.option(
    "--token", envvar="DISCORD_TOKEN", help="Discord token for the bot to declare the commands for.", required=True
)
@_cli.command(name="declare")
def _declare(token: str, schema: pathlib.Path) -> None:  # pyright: ignore[reportUnusedFunction]
    """"""
    commands = _DeclareModel.model_validate(_parse_config(schema), strict=True)
    asyncio.run(_declare_coro(token, commands))


def main() -> None:
    """Entrypoint for Yuyo's commandline tools."""
    _cli()


if __name__ == "__main__":
    main()
