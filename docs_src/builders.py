# -*- coding: utf-8 -*-
# Yuyo Examples - A collection of examples for Yuyo.
# Written in 2023 by Faster Speeding Lucina@lmbyrne.dev
#
# To the extent possible under law, the author(s) have dedicated all copyright
# and related and neighboring rights to this software to the public domain worldwide.
# This software is distributed without any warranty.
#
# You should have received a copy of the CC0 Public Domain Dedication along with this software.
# If not, see <https://creativecommons.org/publicdomain/zero/1.0/>.

# pyright: reportUnusedVariable=none
import hikari

import yuyo


def to_cmd_builder(cmd: hikari.PartialCommand) -> None:
    builder = yuyo.to_builder.to_cmd_builder(cmd)


def to_msg_action_row_builder(row: hikari.MessageActionRowComponent) -> None:
    builder = yuyo.to_builder.to_msg_action_row_builder(row)
