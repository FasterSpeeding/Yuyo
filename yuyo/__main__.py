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
import enum
import json
import logging
import pathlib
import typing
import unicodedata

import hikari

from yuyo import to_builder

from ._internal import localise

try:
    import click
    import dotenv
    import pydantic
    import pydantic.functional_validators
    import pydantic_core
    import toml

except ModuleNotFoundError as _exc:
    raise RuntimeError("Missing necessary dependencies; try reinstalling with the yuyo[cli] flag") from _exc

if typing.TYPE_CHECKING:
    from collections import abc as collections

    from typing_extensions import Self


_EnumT = typing.TypeVar("_EnumT", bound=enum.Enum)
_CONFIG_PARSERS = {
    "json": json.load,
    "toml": toml.load,
    # TODO: yaml?
}
_CONFIG_DUMPERS: dict[str, collections.Callable[[collections.Mapping[str, typing.Any], typing.TextIO], typing.Any]] = {
    "json": lambda value, file: json.dump(value, file, indent=2),
    "toml": toml.dump,
    # TODO: yaml?
}
_DEFUALT_SCHEMA_PATH = pathlib.Path("bot_schema.toml")


def _parse_config(path: pathlib.Path, /) -> collections.Mapping[str, typing.Any]:
    file_type = path.name.rsplit(".", 1)[-1]
    try:
        load = _CONFIG_PARSERS[file_type]

    except KeyError:
        logging.exception(f"Unknown file type {file_type}")
        exit(1)

    with path.open("r") as file:
        return load(file)


def _dump_config(path: pathlib.Path, data: typing.Any, /) -> None:
    file_type = path.name.rsplit(".", 1)[-1]
    try:
        dump = _CONFIG_DUMPERS[file_type]

    except KeyError:
        logging.exception(f"Unknown file type {file_type}")
        exit(1)

    with path.open("w+") as file:
        dump(data, file)


def _to_int(value: int, /) -> int:
    return int(value)


@click.group(name="yuyo")
def _cli() -> None:
    """Terminal commands provided by Yuyo."""
    dotenv.load_dotenv()


@_cli.group(name="commands")
def _commands_group() -> None:
    """A collection of terminal commands for managing application commands."""


_CommandTypes = typing.Literal["message_menu", "slash", "user_menu"]
_COMMAND_TYPES: dict[hikari.CommandType, _CommandTypes] = {
    hikari.CommandType.MESSAGE: "message_menu",
    hikari.CommandType.SLASH: "slash",
    hikari.CommandType.USER: "user_menu",
}

_LOGGER = logging.getLogger("hikari.yuyo")


def _cast_snowflake(value: int) -> hikari.Snowflake:
    if hikari.Snowflake.min() <= value <= hikari.Snowflake.max():
        return hikari.Snowflake(value)

    raise ValueError(f"{value} is not a valid snowflake")


@pydantic.GetPydanticSchema
def _snowflake_schema(
    _source_type: type[typing.Any], _handler: pydantic.GetCoreSchemaHandler
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
        serialization=pydantic_core.core_schema.plain_serializer_function_ser_schema(int),
    )


_Snowflake = typing.Annotated[hikari.Snowflake, _snowflake_schema]


@pydantic.GetPydanticSchema
def _enum_schema(source_type: type[_EnumT], _handler: pydantic.GetCoreSchemaHandler) -> pydantic_core.CoreSchema:
    def _cast_enum(value: typing.Union[str, int]) -> _EnumT:
        result = source_type(value)
        if isinstance(result, source_type):
            return result

        raise ValueError(f"{value!r} is not a valid {source_type.__name__}")

    if issubclass(source_type, int):
        origin_schema = pydantic_core.core_schema.int_schema()
        ser_type = int

    elif issubclass(source_type, str):
        origin_schema = pydantic_core.core_schema.str_schema()
        ser_type = str

    else:
        raise NotImplementedError("Only string and int enums are supported")

    from_schema = pydantic_core.core_schema.chain_schema(
        [origin_schema, pydantic_core.core_schema.no_info_plain_validator_function(_cast_enum)]
    )
    return pydantic_core.core_schema.json_or_python_schema(
        json_schema=from_schema,
        python_schema=pydantic_core.core_schema.union_schema(
            [pydantic_core.core_schema.is_instance_schema(source_type), from_schema]
        ),
        serialization=pydantic_core.core_schema.plain_serializer_function_ser_schema(ser_type),
    )


_Locale = typing.Union[typing.Literal["default"], typing.Annotated[hikari.Locale, _enum_schema]]
_MaybeLocalisedType = typing.Union[str, dict[_Locale, str]]


class _MaybeLocalised(localise.MaybeLocalised[str]):
    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: type[typing.Any], _handler: pydantic.GetCoreSchemaHandler
    ) -> pydantic_core.CoreSchema:
        type_adapter = pydantic.TypeAdapter(_MaybeLocalisedType)
        from_schema = pydantic_core.core_schema.chain_schema(
            [type_adapter.core_schema, pydantic_core.core_schema.with_info_plain_validator_function(cls.pydantic_parse)]
        )
        return pydantic_core.core_schema.json_or_python_schema(
            from_schema,
            pydantic_core.core_schema.union_schema([pydantic_core.core_schema.is_instance_schema(cls), from_schema]),
            serialization=pydantic_core.core_schema.plain_serializer_function_ser_schema(lambda v: v.unparse()),
        )

    @classmethod
    def pydantic_parse(cls, raw_value: _MaybeLocalisedType, info: pydantic_core.core_schema.ValidationInfo, /) -> Self:
        field_name = info.field_name or "<UNKNOWN>"
        return cls.parse(field_name, typing.cast("typing.Union[str, collections.Mapping[str, str]]", raw_value))

    def unparse(self) -> _MaybeLocalisedType:
        if self.localisations:
            value = typing.cast("dict[_Locale, str]", dict(self.localisations))
            value["default"] = self.value

        else:
            value = self.value

        return value

    def _values(self) -> collections.Iterable[str]:
        yield self.value
        yield from self.localisations.values()

    def assert_matches(
        self, pattern: str, match: collections.Callable[[str], bool], /, *, lower_only: bool = False
    ) -> Self:
        if lower_only:

            def is_lower(value: str, /) -> bool:
                if value.lower() != value:
                    raise ValueError(f"Invalid {self.field_name} provided, {value!r} must be lowercase")

                return True

        else:
            is_lower = _always_true

        return super().assert_matches(pattern, lambda value: match(value) and is_lower(value))

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


def _always_true(*args: typing.Any, **kwargs: typing.Any) -> bool:
    return True


class _RenameModel(pydantic.BaseModel):
    commands: dict[typing.Union[str, _Snowflake], _MaybeLocalised]


async def _rename_coro(
    token: str, renames: collections.Mapping[typing.Union[str, _Snowflake], _MaybeLocalised]
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

    async with app.acquire(token, token_type=hikari.TokenType.BOT) as rest:
        application = await rest.fetch_application()
        commands = await rest.fetch_application_commands(application)

        for command in commands:
            names = (
                renames.pop(command.id, None)
                or renames.pop(f"{_COMMAND_TYPES[command.type]}:{command.name}")
                or renames.pop(command.name, None)
            )
            builder = to_builder.to_cmd_builder(command)

            if names:
                names.assert_length(1, 32)
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

    await app.close()


def _cast_rename_flag(value: str) -> tuple[typing.Union[hikari.Snowflake, str], str]:
    try:
        key, value = value.split("=", 1)

    except ValueError:
        raise ValueError(f"Invalid value passed for -c `{value!r}`") from None

    key = key.strip()
    if key.isdigit():
        return hikari.Snowflake(key), value

    return key, value


_DEFAULT_RENAME_FILE = pathlib.Path("./command_renames.toml")


@click.option("--command", "-c", envvar="COMMAND_RENAME", show_envvar=True, multiple=True, type=_cast_rename_flag)
@click.option(
    "--file",
    "-f",
    "schema_file",
    envvar="COMMAND_RENAME_FILE",
    show_envvar=True,
    type=click.Path(exists=True, path_type=pathlib.Path),
)
@click.option(
    "--token",
    envvar="DISCORD_TOKEN",
    show_envvar=True,
    help="Discord token for the bot to rename the commands for.",
    required=True,
)
@_commands_group.command(name="rename")
def _rename(  # pyright: ignore[reportUnusedFunction]
    token: str,
    schema_file: typing.Optional[pathlib.Path],
    command: collections.Sequence[tuple[typing.Union[hikari.Snowflake, str], str]],
) -> None:
    """Rename some of a bot's declared application commands."""
    commands = {key: _MaybeLocalised("name", value, {}) for key, value in command}

    if schema_file is not None or _DEFAULT_RENAME_FILE.exists():
        schema_file = schema_file or _DEFAULT_RENAME_FILE
        parsed = _RenameModel.model_validate(_parse_config(schema_file), strict=True)
        commands.update(parsed.commands)

    asyncio.run(_rename_coro(token, commands))


class _CommandModel(pydantic.BaseModel):
    """Base class for all command models."""

    def to_builder(self) -> hikari.api.CommandBuilder:
        raise NotImplementedError


class _CommandChoiceModel(pydantic.BaseModel):
    """Represents the choices set for an application command's argument."""

    name: _MaybeLocalised
    value: typing.Union[str, int, float]

    @classmethod
    def from_choice(cls, choice: hikari.CommandChoice, /) -> Self:
        name = _MaybeLocalised("name", choice.name, choice.name_localizations)
        return cls(name=name, value=choice.value)

    def to_choice(self) -> hikari.CommandChoice:
        (self.name.assert_length(1, 32).assert_matches(_SCOMMAND_NAME_REG, _validate_slash_name))
        return hikari.CommandChoice(name=self.name.value, name_localizations=self.name.localisations, value=self.value)


_OptionType = typing.Annotated[hikari.OptionType, _enum_schema]
_ChannelType = typing.Annotated[hikari.ChannelType, _enum_schema]


class _CommandOptionModel(pydantic.BaseModel):
    type: _OptionType  # noqa: VNE003
    name: _MaybeLocalised
    description: _MaybeLocalised
    is_required: bool = False
    choices: typing.Optional[list[_CommandChoiceModel]] = pydantic.Field(default_factory=list)
    options: typing.Optional[list[_CommandOptionModel]] = pydantic.Field(default_factory=list)
    channel_types: typing.Optional[list[_ChannelType]] = pydantic.Field(default_factory=list)
    autocomplete: bool = False
    min_value: typing.Union[int, float, None] = None
    max_value: typing.Union[int, float, None] = None
    min_length: typing.Optional[int] = None
    max_length: typing.Optional[int] = None

    @classmethod
    def from_option(cls, opt: hikari.CommandOption, /) -> Self:
        choices = None
        if opt.choices is not None:
            choices = [_CommandChoiceModel.from_choice(choice) for choice in opt.choices]

        options = None
        if opt.options is not None:
            options = [_CommandOptionModel.from_option(opt) for opt in opt.options]

        channel_types = None
        if opt.channel_types is not None:
            channel_types = [hikari.ChannelType(ct) for ct in opt.channel_types]

        name = _MaybeLocalised("name", opt.name, opt.name_localizations)
        description = _MaybeLocalised("description", opt.description, opt.description_localizations)
        return cls(
            type=hikari.OptionType(opt.type),
            name=name,
            description=description,
            choices=choices,
            options=options,
            channel_types=channel_types,
            autocomplete=opt.autocomplete,
            min_value=opt.min_value,
            max_value=opt.max_value,
            min_length=opt.min_length,
            max_length=opt.max_length,
        )

    def to_option(self) -> hikari.CommandOption:
        (self.name.assert_length(1, 32).assert_matches(_SCOMMAND_NAME_REG, _validate_slash_name))
        self.description.assert_length(1, 100)
        return hikari.CommandOption(
            type=self.type,
            name=self.name.value,
            description=self.description.value,
            choices=None if self.choices is None else [choice.to_choice() for choice in self.choices],
            options=None if self.options is None else [opt.to_option() for opt in self.options],
            channel_types=self.channel_types,
            autocomplete=self.autocomplete,
            min_value=self.min_value,
            max_value=self.max_value,
            name_localizations=self.name.localisations,
            description_localizations=self.description.localisations,
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
    type: typing.Annotated[  # noqa: VNE003
        typing.Literal[hikari.CommandType.SLASH], pydantic.PlainSerializer(_to_int)
    ] = hikari.CommandType.SLASH
    name: _MaybeLocalised
    description: _MaybeLocalised
    id: typing.Optional[_Snowflake] = None  # noqa: VNE003
    default_member_permissions: typing.Optional[int] = None
    is_dm_enabled: bool = True
    is_nsfw: bool = False
    options: list[_CommandOptionModel] = pydantic.Field(default_factory=list)

    @classmethod
    def from_builder(cls, builder: hikari.api.SlashCommandBuilder, /) -> Self:
        name = _MaybeLocalised("name", builder.name, builder.name_localizations)
        description = _MaybeLocalised("description", builder.description, builder.description_localizations)

        default_member_permissions = None
        if builder.default_member_permissions is not hikari.UNDEFINED:
            default_member_permissions = builder.default_member_permissions

        return cls(
            type=hikari.CommandType.SLASH,
            name=name,
            description=description,
            id=None if builder.id is hikari.UNDEFINED else builder.id,
            default_member_permissions=default_member_permissions,
            is_dm_enabled=True if builder.is_dm_enabled is hikari.UNDEFINED else builder.is_dm_enabled,
            is_nsfw=False if builder.is_nsfw is hikari.UNDEFINED else builder.is_nsfw,
            options=[_CommandOptionModel.from_option(opt) for opt in builder.options],
        )

    def to_builder(self) -> hikari.api.SlashCommandBuilder:
        default_member_permissions = hikari.UNDEFINED
        if self.default_member_permissions is not None:
            default_member_permissions = self.default_member_permissions

        (self.name.assert_length(1, 32).assert_matches(_SCOMMAND_NAME_REG, _validate_slash_name))
        self.description.assert_length(1, 100)
        return hikari.impl.SlashCommandBuilder(
            name=self.name.value,
            description=self.description.value,
            id=hikari.UNDEFINED if self.id is None else hikari.Snowflake(self.id),
            default_member_permissions=default_member_permissions,
            is_dm_enabled=self.is_dm_enabled,
            is_nsfw=self.is_nsfw,
            name_localizations=self.name.localisations,
            description_localizations=self.description.localisations,
            options=[opt.to_option() for opt in self.options],
        )


class _DeclareMenuCmdModel(_CommandModel):
    type: typing.Annotated[  # noqa: VNE003
        typing.Literal[hikari.CommandType.MESSAGE, hikari.CommandType.USER], pydantic.PlainSerializer(_to_int)
    ]
    name: _MaybeLocalised
    id: typing.Optional[_Snowflake] = None  # noqa: VNE003
    default_member_permissions: typing.Optional[int] = None
    is_dm_enabled: bool = True
    is_nsfw: bool = False

    @classmethod
    def from_builder(cls, builder: hikari.api.ContextMenuCommandBuilder, /) -> Self:
        name = _MaybeLocalised("name", builder.name, builder.name_localizations)

        default_member_permissions = None
        if builder.default_member_permissions is not hikari.UNDEFINED:
            default_member_permissions = builder.default_member_permissions

        return cls(
            type=typing.cast("typing.Literal[hikari.CommandType.MESSAGE, hikari.CommandType.USER]", builder.type),
            name=name,
            id=None if builder.id is hikari.UNDEFINED else builder.id,
            default_member_permissions=default_member_permissions,
            is_dm_enabled=True if builder.is_dm_enabled is hikari.UNDEFINED else builder.is_dm_enabled,
            is_nsfw=False if builder.is_nsfw is hikari.UNDEFINED else builder.is_nsfw,
        )

    def to_builder(self) -> hikari.api.ContextMenuCommandBuilder:
        default_member_permissions = hikari.UNDEFINED
        if self.default_member_permissions is not None:
            default_member_permissions = self.default_member_permissions

        self.name.assert_length(1, 31)
        return hikari.impl.ContextMenuCommandBuilder(
            type=self.type,
            name=self.name.value,
            id=hikari.UNDEFINED if self.id is None else hikari.Snowflake(self.id),
            default_member_permissions=default_member_permissions,
            is_dm_enabled=self.is_dm_enabled,
            is_nsfw=self.is_nsfw,
            name_localizations=self.name.localisations,
        )


_CommandModelIsh = typing.Union[_DeclareSlashCmdModel, _DeclareMenuCmdModel]


class _DeclareModel(pydantic.BaseModel):
    commands: list[_CommandModelIsh]


async def _declare_coro(token: str, schema: _DeclareModel) -> None:
    app = hikari.RESTApp()
    await app.start()

    async with app.acquire(token, token_type=hikari.TokenType.BOT) as rest:
        application = await rest.fetch_application()
        await rest.set_application_commands(application.id, [cmd.to_builder() for cmd in schema.commands])

    await app.close()


@click.option(
    "--file",
    "-f",
    "schema",
    default=_DEFUALT_SCHEMA_PATH,
    envvar="BOT_SCHEMA_FILE",
    show_envvar=True,
    help="",
    type=click.Path(exists=True, path_type=pathlib.Path),
)
@click.option(
    "--token",
    envvar="DISCORD_TOKEN",
    show_envvar=True,
    help="Discord token for the bot to declare the commands for.",
    required=True,
)
@_commands_group.command(name="declare")
def _declare(token: str, schema: pathlib.Path) -> None:  # pyright: ignore[reportUnusedFunction]
    """Declare a bot's application commands based on a schema."""
    commands = _DeclareModel.model_validate(_parse_config(schema), strict=True)
    asyncio.run(_declare_coro(token, commands))


async def _fetch_coro(token: str) -> list[_CommandModelIsh]:
    commands: list[_CommandModelIsh] = []
    app = hikari.impl.RESTApp()
    # TODO: allow doing this all in one async with statement.
    # TODO: support using bearer tokens.
    # TODO: support guild specific commands.
    await app.start()

    async with app.acquire(token, token_type=hikari.TokenType.BOT) as rest:
        application = await rest.fetch_application()
        raw_commands = await rest.fetch_application_commands(application)

    await app.close()

    for command in raw_commands:
        if isinstance(command, hikari.SlashCommand):
            builder = to_builder.to_slash_cmd_builder(command)
            commands.append(_DeclareSlashCmdModel.from_builder(builder))

        elif isinstance(command, hikari.ContextMenuCommand):
            builder = to_builder.to_context_menu_builder(command)
            commands.append(_DeclareMenuCmdModel.from_builder(builder))

        else:
            raise NotImplementedError(f"Unsupported command type {command.type}")

    return commands


@_commands_group.command("fetch")
@click.option(
    "--file",
    "-f",
    "schema",
    default=_DEFUALT_SCHEMA_PATH,
    envvar="BOT_SCHEMA_FILE",
    show_envvar=True,
    help="",
    type=click.Path(path_type=pathlib.Path),
)
@click.option(
    "--token",
    envvar="DISCORD_TOKEN",
    show_envvar=True,
    help="Discord token for the bot to fetch the command schema for.",
    required=True,
)
@click.option(
    "--exclude-id",
    "--ei",
    is_flag=True,
    default=False,
    help="Whether to exclude command IDs from the output",
    required=True,
)
def _fetch_schema(schema: pathlib.Path, token: str, exclude_id: bool) -> None:  # pyright: ignore[reportUnusedFunction]
    """Fetch a bot's current command schema."""
    commands = asyncio.run(_fetch_coro(token))
    data = _DeclareModel(commands=commands)

    if exclude_id:
        for command in data.commands:
            command.id = None

    _dump_config(schema, data.model_dump())


def main() -> None:
    """Entrypoint for Yuyo's commandline tools."""
    _cli()


if __name__ == "__main__":
    main()
