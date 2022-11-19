# -*- coding: utf-8 -*-
# cython: language_level=3
# BSD 3-Clause License
#
# Copyright (c) 2020-2022, Faster Speeding
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
"""A collection of utility functions and classes designed to enhances Hikari."""

from __future__ import annotations

__all__: typing.Sequence[str] = [
    "AbstractComponentExecutor",
    "AbstractReactionHandler",
    "ActionRowExecutor",
    "AsgiAdapter",
    "AsgiBot",
    "Backoff",
    "ChildActionRowExecutor",
    "ChunkRequestFinishedEvent",
    "ChunkTracker",
    "ComponentClient",
    "ComponentContext",
    "ComponentExecutor",
    "ComponentPaginator",
    "ErrorManager",
    "FinishedChunkingEvent",
    "InteractiveButtonBuilder",
    "MultiComponentExecutor",
    "ReactionClient",
    "ReactionHandler",
    "ReactionPaginator",
    "SelectMenuBuilder",
    "ShardFinishedChunkingEvent",
    "WaitForExecutor",
    "aenumerate",
    "as_child_executor",
    "as_component_callback",
    "as_reaction_callback",
    "asgi",
    "async_paginate_string",
    "backoff",
    "chunk_tracker",
    "components",
    "paginate_string",
    "pagination",
    "reactions",
    "sync_paginate_string",
]

import typing

from .asgi import *
from .backoff import *
from .chunk_tracker import *
from .components import *
from .list_status import *
from .pagination import *
from .reactions import *

WaitForComponent = WaitForExecutor
