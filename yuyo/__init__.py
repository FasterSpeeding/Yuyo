# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Copyright (c) 2020-2023, Faster Speeding
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

__all__: list[str] = [
    "ActionRowExecutor",
    "AsgiAdapter",
    "AsgiBot",
    "Backoff",
    "BotsGGService",
    "ChunkRequestFinishedEvent",
    "ChunkTracker",
    "ComponentClient",
    "ComponentContext",
    "ComponentExecutor",
    "ComponentPaginator",
    "DiscordBotListService",
    "ErrorManager",
    "FinishedChunkingEvent",
    "MultiComponentExecutor",
    "ReactionClient",
    "ReactionHandler",
    "ReactionPaginator",
    "ServiceManager",
    "ShardFinishedChunkingEvent",
    "TopGGService",
    "WaitForExecutor",
    "aenumerate",
    "asgi",
    "async_paginate_string",
    "backoff",
    "chunk_tracker",
    "components",
    "links",
    "paginate_string",
    "pagination",
    "reactions",
    "sync_paginate_string",
    "to_builder",
]

from . import links
from . import to_builder
from .asgi import AsgiAdapter
from .asgi import AsgiBot
from .backoff import Backoff
from .backoff import ErrorManager
from .chunk_tracker import ChunkRequestFinishedEvent
from .chunk_tracker import ChunkTracker
from .chunk_tracker import FinishedChunkingEvent
from .chunk_tracker import ShardFinishedChunkingEvent
from .components import ActionRowExecutor
from .components import ComponentClient
from .components import ComponentContext
from .components import ComponentExecutor
from .components import ComponentPaginator
from .components import MultiComponentExecutor
from .components import WaitForExecutor
from .list_status import BotsGGService
from .list_status import DiscordBotListService
from .list_status import ServiceManager
from .list_status import TopGGService
from .pagination import aenumerate
from .pagination import async_paginate_string
from .pagination import paginate_string
from .pagination import sync_paginate_string
from .reactions import ReactionClient
from .reactions import ReactionHandler
from .reactions import ReactionPaginator
