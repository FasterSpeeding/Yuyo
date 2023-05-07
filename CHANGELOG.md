# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
## [1.14.2] - 2023-05-08
### Fixed
- The fields for a [ModalOptions][yuyo.modals.ModalOptions] are now correctly
  tracked when added to a [Modal][yuyo.modals.Modal] instance and are
  no-longer erroneously tracked as static fields for `type(modal)`.

## [1.14.1] - 2023-05-03
### Changed
- [ComponentClient.register_executor][yuyo.components.ComponentClient.register_executor]
  now raises a `ValueError` if any of the custom IDs or the message ID is
  already registered to better match `register_modal`.
- [ComponentClient.deregister_executor][yuyo.components.ComponentClient.deregister_executor]
  now raises a `KeyError` if the component isn't registered to better match the
  other deregister methods.

### Removed
- Erroneous `prefix_match` parameter from [yuyo.modals.with_text_input][] which
  should've been removed in `v1.14.0`

## [1.14.0] - 2023-05-03
### Added
- `authors` option to
  [components.ActionColumnExecutor.\_\_init\_\_][yuyo.components.ActionColumnExecutor.__init__].
- Functions for generating Discord Oauth2 authorize links and bot invite links
  to [yuyo.links][].
- [ActionColumnExecutor.with_interactive_button][yuyo.components.ActionColumnExecutor.with_interactive_button].
- [ActionColumnExecutor.with_static_interactive_button][yuyo.components.ActionColumnExecutor.with_static_interactive_button].
- [ActionColumnExecutor.with_mentionable_menu][yuyo.components.ActionColumnExecutor.with_mentionable_menu].
- [ActionColumnExecutor.with_static_mentionable_menu][yuyo.components.ActionColumnExecutor.with_static_mentionable_menu].
- [ActionColumnExecutor.with_role_menu][yuyo.components.ActionColumnExecutor.with_role_menu].
- [ActionColumnExecutor.with_static_role_menu][yuyo.components.ActionColumnExecutor.with_static_role_menu].
- [ActionColumnExecutor.with_user_menu][yuyo.components.ActionColumnExecutor.with_user_menu].
- [ActionColumnExecutor.with_static_user_menu][yuyo.components.ActionColumnExecutor.with_static_user_menu].
- [ActionColumnExecutor.with_channel_menu][yuyo.components.ActionColumnExecutor.with_channel_menu].
- [ActionColumnExecutor.with_text_menu][yuyo.components.ActionColumnExecutor.with_text_menu].
- [ActionColumnExecutor.with_static_text_menu][yuyo.components.ActionColumnExecutor.with_static_text_menu].
- [yuyo.components.column_template][] shorthand function for creating a column subclass.

### Changed
- Message component custom IDs are now defaulted to a constant ID that's generated
  from the function's path (which includes the relevant module and class
  qualnames) when added using the `as_` descriptors in [yuyo.components][].
- The `id_metadata` field in
  [components.ActionColumnExecutor.\_\_init\_\_][yuyo.components.ActionColumnExecutor.__init__]
  now also supports using a component callback's name in the class' namespace
  as the key (specifically when it was added using one of the `as_`
  descriptors).
- The auto-generated default UUID custom IDs now only consist of the UUID's hex
  (without any `-`), bringing the length down from 36 chars to 32.
- The descriptors returned by the `as_` decorators in [yuyo.components][] are
  now hidden when accessed directly on classes. The decorated callback will now
  be directly exposed as the class attribute instead.

### Fixed
- [ActionColumnExecutor][yuyo.components.ActionColumnExecutor] and
  [Modal][yuyo.modals.Modal] both now properly relay
  `__init_subclass__` keyword arguments when being used in mixed inheritance.

### Removed
- `yuyo.components.with_static_interactive_button`
- `yuyo.components.with_static_link_button`
- `yuyo.components.with_static_select_menu`
- `yuyo.components.with_static_channel_menu`
- `yuyo.components.with_static_text_menu`
- The following deprecated functionality and aliases:
    * `ActionRowExecutor` in favour of the new action column executor.
    * Allowing callback to be passed as the first argument and type as the
    second argument for
    [ActionColumnExecutor.add_select_menu][yuyo.components.ActionColumnExecutor.add_select_menu], and
    [ActionColumnExecutor.add_static_select_menu][yuyo.components.ActionColumnExecutor.add_static_select_menu].
    * `timeout` keyword argument from
    [ComponentExecutor.\_\_init\_\_][yuyo.components.ComponentExecutor.__init__],
    [ActionColumnExecutor.\_\_init\_\_][yuyo.components.ActionColumnExecutor.__init__],
    and [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__].
    * `prefix_match` keyword argument from
    [Modal.add_static_text_input][yuyo.modals.Modal.add_static_text_input],
    [Modal.add_text_input][yuyo.modals.Modal.add_text_input],
    [modals.with_static_text_input][yuyo.modals.with_static_text_input],
    [modals.with_text_input][yuyo.modals.with_text_input],
    and [modals.text_input][yuyo.modals.text_input].
    * `ComponentContext.select_channels`
    * `ComponentContext.select_roles`
    * `ComponentContext.select_texts`
    * `ComponentContext.select_users`
    * `ComponentContext.select_members`
    * `ComponentClient.set_constant_id`
    * `ComponentClient.get_constant_id`
    * `ComponentClient.remove_constant_id`
    * `ComponentClient.with_constant_id`
    * `ComponentClient.set_executor`
    * `ComponentClient.get_executor`
    * `ComponentClient.remove_executor`
    * `AbstractComponentExecutor.has_expired`
    * `AbstractComponentExecutor.timeout`
    * `ComponentExecutor.has_expired`
    * `ComponentExecutor.timeout`
    * `ActionColumnExecutor.timeout`
    * `ActionColumnExecutor.has_expired`
    * `ActionColumnExecutor.add_button`
    * `ActionColumnExecutor.add_interative_button`
    * `ActionColumnExecutor.add_static_button`
    * `ActionColumnExecutor.add_static_interative_button`
    * `ActionColumnExecutor.with_static_button`
    * `ActionColumnExecutor.with_static_interative_button`
    * `ActionColumnExecutor.with_static_select_menu`
    * `ActionColumnExecutor.add_channel_select`
    * `ActionColumnExecutor.add_static_channel_select`
    * `ActionColumnExecutor.with_static_channel_select`
    * `ActionColumnExecutor.add_text_select`
    * `ActionColumnExecutor.add_static_text_select`
    * `ComponentPaginator.builder`
    * `ComponentPaginator.add_row`
    * `components.with_static_button`
    * `components.with_static_interative_button`
    * `components.with_static_channel_select`
    * `InviteLink.fetch`
    * `InviteLink.get`
    * `MessageLink.fetch`
    * `MessageLink.get`
    * `TemplateLink.fetch`
    * `WebhookLink.fetch`
    * `modals.AbstractTimeout`
    * `modals.BasicTimeout`
    * `modals.NeverTimeout`
    * `ModalClient.set_modal`
    * `ModalClient.remove_modal`
    * `timeouts.BasicTimeout`
    * `yuyo.BasicTimeout`

## [1.13.0a1] - 2023-04-25
### Added
- [components.Paginator][yuyo.components.Paginator] alias of
  [components.ComponentPaginator][yuyo.components.ComponentPaginator].
- [reactions.Handler][yuyo.reactions.Handler] alias of
  [reactions.ReactionHandler][yuyo.reactions.ReactionHandler].
- [reactions.Paginator][yuyo.reactions.Paginator] alias of
  [reactions.ReactionPaginator][yuyo.reactions.ReactionPaginator].

### Changed
- [ComponentPaginator][yuyo.components.ComponentPaginator] now implements
  [ActionColumnExecutor][yuyo.components.ActionColumnExecutor] rather than
  `ActionRowExecutor`.
  The main (breaking) consequence of this change is that you now need to pass
  `pagintor.rows` to `components` rather than passing the paginator itself to
  `component`.
- Moved out the paginator logic used by [yuyo.components.ComponentPaginator][]
  and [yuyo.reactions.ReactionPaginator][] to the new
  [yuyo.pagination.Paginator][] class.

### Deprecated
- `yuyo.components.ActionRowExecutor` in favour of the action column executor.
- `ActionColumnExecutor.add_row`.

### Fixed
- [reactions.Client][yuyo.reactions.Client] now correctly points towards
  [reactions.ReactionClient][yuyo.reactions.ReactionClient].
- Some edge cases where the paginators were sending the current page in response
  to a reaction/interaction instead of giving a noop response or just not
  responding.

### Removed
- `timeout` argument from [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__].
- `"WaitFor"` from `yuyo.components.__all__`.

## [1.12.0a1] - 2023-04-24
### Added
- `ephemeral_default` option to [ActionColumnExecutor.\_\_init\_\_][yuyo.components.ActionColumnExecutor.__init__].
- Shorthand methods and functions for adding/declaring mentionable, role and user menus:
    * [components.as_mentionable_menu][yuyo.components.as_mentionable_menu]
    * [components.as_role_menu][yuyo.components.as_role_menu]
    * [components.as_user_menu][yuyo.components.as_user_menu]
    * [ActionColumnExecutor.add_mentionable_menu][yuyo.components.ActionColumnExecutor.add_mentionable_menu]
    * [ActionColumnExecutor.add_static_mentionable_menu][yuyo.components.ActionColumnExecutor.add_static_mentionable_menu]
    * [ActionColumnExecutor.add_role_menu][yuyo.components.ActionColumnExecutor.add_role_menu]
    * [ActionColumnExecutor.add_static_role_menu][yuyo.components.ActionColumnExecutor.add_static_role_menu]
    * [ActionColumnExecutor.add_user_menu][yuyo.components.ActionColumnExecutor.add_user_menu]
    * [ActionColumnExecutor.add_static_user_menu][yuyo.components.ActionColumnExecutor.add_static_user_menu]
    * `ActionRowExecutor.add_mentionable_menu`
    * `ActionRowExecutor.add_role_menu`
    * `ActionRowExecutor.add_user_menu`

### Changed
- [ActionColumnExecutor][yuyo.components.ActionColumnExecutor] now allows overriding
  inherited component class descriptors.
- The `add_static` methods on [ActionColumnExecutor][yuyo.components.ActionColumnExecutor]
  now override any previously added sub-component with the same match ID rather than
  append a duplicate entry.

### Fixed
- [ActionColumnExecutor][yuyo.components.ActionColumnExecutor] now respects the order
  component descriptors were defined in on the class.

### [1.11.2a1] - 2023-04-10
### Added
- Support for parsing message links to [yuyo.links][].

### Changed
- Added support for `ptb.` and `canary.` links to [yuyo.links][].
- Modals now default the per-field custom IDs (i.e. for text components) to the parameter's
  name (attribute name for [ModalOptions][yuyo.modals.ModalOptions] fields), if set.
- Renamed the link get and fetch methods:
    * `InviteLink.fetch` to [InviteLink.fetch_invite][yuyo.links.InviteLink.fetch_invite]
    * `InviteLink.get` to [InviteLink.get_invite][yuyo.links.InviteLink.get_invite]
    * `MessageLink.fetch` to [MessageLink.fetch_message][yuyo.links.MessageLink.fetch_message]
    * `MessageLink.get` to [MessageLink.get_message][yuyo.links.MessageLink.get_message]
    * `TemplateLink.fetch` to [TemplateLink.fetch_template][yuyo.links.TemplateLink.fetch_template]
    * `WebhookLink.fetch` to [WebhookLink.fetch_webhook][yuyo.links.WebhookLink.fetch_webhook]

### Fixed
- [ModalOptions][yuyo.modals.ModalOptions] attributes now correctly expose the values passed to
  the modal rather than internal descriptors.
- [ChunkTracker.set_auto_chunk_members][yuyo.chunk_tracker.ChunkTracker.set_auto_chunk_members]
  now correctly disables auto chunking when [False][] is passed after it has been previously
  enabled. This now also always changes the configuration for `chunk_presences`.
- Some typoed function names which were missing the "c" in "interactive".
- [AsgiBot.start][yuyo.asgi.AsgiBot.start] and [AsgiBot.close][yuyo.asgi.AsgiBot.close]
  will now call the startup and shutdown callbacks respectively when `asgi_managed=False`.

### [1.11.1a1] - 2023-04-05
### Changed
- `callback` and `type` have been flipped (making `type` the first argument and `callback`
   the second one) for the following functions:
    * `ActionRowExecutor.add_select_menu`
    * [ActionColumnExecutor.add_select_menu][yuyo.components.ActionColumnExecutor.add_select_menu]
    * [ActionColumnExecutor.add_static_select_menu][yuyo.components.ActionColumnExecutor.add_static_select_menu]
    * `with_static_select_menu`
- Renamed the component context select menu data properties:
    * `ComponentContext.select_channels` to [ComponentContext.selected_channels][yuyo.components.ComponentContext.selected_channels]
    * `ComponentContext.select_roles` to [ComponentContext.selected_roles][yuyo.components.ComponentContext.selected_roles]
    * `ComponentContext.select_texts` to [ComponentContext.selected_texts][yuyo.components.ComponentContext.selected_texts]
    * `ComponentContext.select_users` to [ComponentContext.selected_users][yuyo.components.ComponentContext.selected_users]
    * `ComponentContext.select_members` to [ComponentContext.selected_members][yuyo.components.ComponentContext.selected_members]

### Deprecated
- Passing `callback` as the first argument when adding a select menu to a component executor or column.
- The `with_{}` methods on [yuyo.components.ActionColumnExecutor][].

### Fixed
- [yuyo.modals.modal][] and [yuyo.modals.as_modal][] both now properly support DI for the
  modal's callback.
- [yuyo.modals.as_modal][] and [yuyo.modals.as_modal_template][] both now allow passing
  `parse_signature` typing wise.
- [ComponentClient.register_executor][yuyo.components.ComponentClient.register_executor]
  now defaults to unlimited uses instead of 1 use.

### [1.11.0a1] - 2023-04-02
### Added
- A static timeout implementation.
- Support for custom ID prefix matching to the Message component executors.
- Message components have support for loading components from class attributes again.
  Support for this has been implemented through [yuyo.components.ActionColumnExecutor][] this time.
- [yuyo.components.SingleExecutor][] and [yuyo.components.as_single_executor][]
  to allow registering a component executor with a single callback.
- New component handling system to the component client which allows component executors to be
  used statelessly. This moves to using the classes in [yuyo.timeouts][] to handle timeouts
  (rather than the component executors) and makes binding to a specific message optional.
  This consists of [ComponentClient.register_executor][yuyo.components.ComponentClient.register_executor]
  and [ComponentClient.deregister_executor][yuyo.components.ComponentClient.deregister_executor].
- `yuyo.components.with_static_text_menu` decorator for declaring a static text select menu on
  a [ActionColumnExecutor][yuyo.components.ActionColumnExecutor] subclass.
- `options` parameter to `ActionColumnExecutor.add_static_text_select`,
  `ActionColumnExecutor.add_text_select`, and `ActionRowExecutor.add_text_select` for passing
  option builders.
- `ComponentContext.id_match` and `ModalContext.id_metadata` convenient properties for getting
  the matching and metadata parts of the component's custom ID.
- `Modal.id_match`, `Modal.id_metadata` and [ModalContext.component_ids][yuyo.modals.ModalContext.component_ids]
  convenience properties for getting the matching and metadata parts of the Modal's top-level
  custom ID and the sub-component custom IDs.
- [ComponentExecutor.set_callback][yuyo.components.ComponentExecutor.set_callback] and
  [ComponentExecutor.with_callback][yuyo.components.ComponentExecutor.with_callback] now
  both raise [ValueError][] if `":"` is present in `custom_id`.
- `id_metadata` option to
  [ActionColumnExecutor.\_\_init\_\_][yuyo.components.ActionColumnExecutor.__init__] and
  [Modal.\_\_init\_\_][yuyo.modals.Modal.__init__] to allow for setting the
  ID metadata of components per-init.

### Changed
- Bumped the minimum Hikari version to `2.0.0.dev118`.
  Some of the breaking component changes listed in Hikari's
  [change log](https://docs.hikari-py.dev/en/latest/changelog/#dev118-2023-04-02)
  around the component builders effect Yuyo's component executors.
- Prefix matching behaviour is now always enabled for both modals and components.
- Message components now split by `":"` for prefix matching like the modals client.
- Marked most deprecated timeout class aliases using `typing.deprecated`.
  (only `yuyo.modals.AbstractTimeout` was skipped).
- [yuyo.components.WaitForExecutor][] now inherits from [yuyo.components.WaitForExecutor][]
  and should also be passed to `timeout=`.
- [ActionColumnExecutor.rows][yuyo.components.ActionColumnExecutor.rows] now returns
  [hikari.api.MessageActionRowBuilder][hikari.api.special_endpoints.MessageActionRowBuilder].
- Message components will now give a "timed-out" ephemeral initial response when
  [ExecutorClosed][yuyo.components.ExecutorClosed] is raised without any response.
- The `authors` field is now optional (defaulting to public) for
  [WaitForExecutor.\_\_init\_\_][yuyo.components.WaitForExecutor.__init__],
  [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__], and
  [ReactionPaginator.\_\_init\_\_][yuyo.reactions.ReactionPaginator.__init__].
- Renamed `yuyo.timeouts.BasicTimeout` to [yuyo.timeouts.SlidingTimeout][].
- Renamed `ModalClient.set_modal` to [Modal.register_modal][yuyo.modals.ModalClient.register_modal].
- Renamed `ModalClient.remove_modal` to [Modal.deregister_modal][yuyo.modals.ModalClient.deregister_modal].
- Renamed `ComponentClient.get_executor` to [ComponentClient.get_executor_for_message][yuyo.components.ComponentClient.get_executor_for_message].
- Renamed `ComponentClient.remove_executor` to [ComponentClient.deregister_message][yuyo.components.ComponentClient.deregister_message].
- Renamed `add_` and `with_` component methods to better match Hikari's new naming scheme:
    * `ActionRowExecutor.add_button` to `.add_interactive_button`
    * `ActionRowExecutor.add_channel_select` to `.add_channel_menu`
    * `ActionRowExecutor.add_text_select` to `.add_text_menu`
    * `ActionColumnExecutor.add_button` to `.add_interactive_button`
    * `ActionColumnExecutor.add_channel_select` to `.add_channel_menu`
    * `ActionColumnExecutor.add_text_select` to `.add_text_menu`
    * `ActionColumnExecutor.add_static_button` to `.add_static_interactive_button`
    * `ActionColumnExecutor.with_static_button` to `.with_static_interactive_button`
    * `ActionColumnExecutor.add_static_channel_select` to `.add_static_channel_menu`
    * `ActionColumnExecutor.with_static_channel_select` to `.with_static_channel_menu`
    * `ActionColumnExecutor.add_static_text_select` to `.add_static_text_menu`
    * `yuyo.components.with_static_button` to `.with_static_interactive_button`
    * `yuyo.components.with_static_channel_select` to `.with_static_channel_menu`

### Deprecated
- The constant ID component handling system.
  This has been replaced with passing [yuyo.components.SingleExecutor][] to
  [ComponentClient.register_executor][yuyo.components.ComponentClient.register_executor].
- Passing `timeout` to [ComponentExecutor.\_\_init\_\_][yuyo.components.ComponentExecutor.__init__],
  `ActionRowExecutor.__init__`,
  [ActionColumnExecutor.\_\_init\_\_][yuyo.components.ActionColumnExecutor.__init__], and
  [ComponentPaginator.\_\_init\_\_][yuyo.components.ComponentPaginator.__init__].
  This has been replaced by passing `timeout` to
  [ComponentClient.register_executor][yuyo.components.ComponentClient.register_executor]
  to allow for the stateless reuse of component executors.
- `AbstractComponentExecutor.has_expired`.
- `ActionRowExecutor.is_full`.
- `ComponentClient.set_executor`, this has been replaced by
  [Component.register_executor][yuyo.components.ComponentClient.register_executor].
- Passing `yuyo.components.ActionRowExecutor` to `ActionColumnExecutor.add_row`. This
  now takes [hikari.api.MessageActionRowBuilder][hikari.api.special_endpoints.MessageActionRowBuilder].
- The `prefix_match` parameter as this is now always enabled.

### Removed
- `yuyo.modals.NoDefault`.

### [1.10.1a1] - 2023-03-25
### Added
- Some convenience properties to [ComponentContext][yuyo.components.ComponentContext] for getting select
  menu values:
    * `.select_channels`
    * `.select_roles`
    * `.select_texts`
    * `.select_users`
    * `.select_members`
- The [yuyo.components.Context][] and [yuyo.modals.Context][] aliases.
- The [yuyo.components.Client][], [yuyo.modals.Client][], and [yuyo.reactions.Client][] aliases.

### Changed
- A Modal text input's `default` will now also be used for `value` when `value` is left undefined and
  `default` is a string of `<=4000` characters.
- Increased the default timeout for modals to 2 minutes.

### Fixed
- Text select menus will no-longer lead to an error being returned by Discord when `max_values` is
  greater then the count of its choices.

## [1.10.0a1] - 2023-03-20
### Added
- Support for declaring modal options in the modal callback's signature.

### Changed
- Moved `yuyo.modals.AbstractTimeout`, `yuyo.modals.BasicTimeout` and `yuyo.modals.NeverTimeout`
  to new [yuyo.timeouts][] module.

### Deprecated
- `yuyo.modals.AbstractTimeout`, `yuyo.modals.BasicTimeout` and `yuyo.modals.NeverTimeout` as deprecated aliases

### Fixed
- Modals now correctly default to a timeout duration of 10 seconds rather than 10 days.

### Removed
- The deprecated `yuyo.components.MultiComponentExecutor` and `yuyo.components.ChildActionRowExecutor`
  types.
- `ActionRowExecutor.add_button` can no-longer be used to add link buttons.
- [yuyo.modals.Modal][] subclasses will no-longer inherits fields.

## [1.9.1a1] - 2023-03-07
### Added
- Re-exposed `yuyo.reactions.EventT` as [yuyo.reactions.ReactionEventT][].

### Changed
- `token_type` now defaults to `"Bot"` when a string token is passed for
  [AsgiBot.\_\_init\_\_][yuyo.asgi.AsgiBot.__init__].

### Fixed
- [yuyo.modals.modal][] and [yuyo.modals.as_modal][] no-longer lead to Alluka's type-hint introspection
  raising an exception.
- Handling of defaulting empty modal text inputs.
- Add `type` property to `yuyo.components.ActionRowExecutor` and
  `yuyo.components.ChildActionRowExecutor` to fix compatibility with `Hikari>=2.0.0.dev117`.

## [1.9.0a1] - 2023-02-27
### Added
- `from_tanjun` convenience classmethods for initialising from a Tanjun client to
  [ComponentClient][yuyo.modals.ModalClient], [ModalClient][yuyo.modals.ModalClient],
  [ReactionClient][yuyo.reactions.ReactionClient], and [ServiceManager][yuyo.list_status.ServiceManager].
- `alluka` keyword-argument to to `from_gateway_bot` and `from_rest_bot` methods on
  [ComponentClient][yuyo.modals.ModalClient], [ModalClient][yuyo.modals.ModalClient], and
  [ReactionClient][yuyo.reactions.ReactionClient].

### Changed
- `timeout` is now keyword-only for [ChunkTracker.\_\_init\_\_][yuyo.chunk_tracker.ChunkTracker.__init__].
- The Alluka bound clients ([ComponentClient][yuyo.modals.ModalClient],
  [ModalClient][yuyo.modals.ModalClient], and [ReactionClient][yuyo.reactions.ReactionClient])
  now all register themselves as type dependencies when they're not passed a 3rd party client.

### Fixed
- Prefix matched custom IDs are now correctly lower priority for modals.
- [AsgiBot.remove_shutdown_callback][yuyo.asgi.AsgiBot.remove_shutdown_callback] and
  [AsgiBot.remove_startup_callback][yuyo.asgi.AsgiBot.remove_startup_callback] now raise a [ValueError][]
  if the callback isn't registered (as per the documented behaviour) instead of silently passing.

### Removed
- Unnecessary entries from module `__all__`s (i.e. type hints, abstract classes, base classes and
  internal signal error classes).
- Type variables are no-longer publicly exposed other than a couple callback types.

## [1.8.0a1.post1] - 2023-02-23
### Fixed
- The [yuyo.components.ComponentPaginator][] will no-longer send a new message with "MESSAGE_UPDATE" as
  the content when the last entry button is pressed for the first time instead of marking it as loading.
- The [yuyo.components.ComponentPaginator][] will no-longer create a new message with "MESSAGE_UPDATE"
  as the content instead of giving a noop update response.

## [1.8.0a1] - 2023-02-23
### Added
- `timeout` config to [ChunkTracker.\_\_init\_\_][yuyo.chunk_tracker.ChunkTracker.__init__].
- `bot_managed` config to [ComponentClient.from_rest_bot][yuyo.components.ComponentClient.from_rest_bot].
- [ComponentContext.create_modal_response][yuyo.components.ComponentContext.create_modal_response] method.
- Support for modals in `yuyo.modals`.
- [yuyo.components.ActionColumnExecutor][] which handles building and executing multiple message
  action row components and also introduces a class template system for message components in a similar
  fashion to modals.

### Changed
- The `response_type` argument is now keyword only and defaults to
  [ResponseType.MESSAGE_CREATE][hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE] in
  [ComponentContext.create_initial_response][yuyo.components.ComponentContext.create_initial_response].
- The `defer_type` argument is now keyword only and defaults to
  [ResponseType.DEFERRED_MESSAGE_CREATE][hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_CREATE]
  in [ComponentContext.defer][yuyo.components.ComponentContext.defer].

### Deprecated
- `yuyo.components.MultiComponentExecutor` and `yuyo.components.ChildActionRowExecutor`.
  [yuyo.components.ActionColumnExecutor][] should be used instead.
- Using `ActionRowExecutor.add_button` to add specifically link buttons.
  `ActionRowExecutor.add_link_button` should be used instead.

### Fixed
- The `add_{}_button` methods on [ComponentPaginator][yuyo.components.ComponentPaginator] now ignore
  `emoji` when `label` is passed to avoid erroring when users don't explicitly unset the
  default for `emoji`.

### Removed
- The `AbstractReactionHandler.last_triggered` and `ReactionHandler.timeout` properties as
  these were leaking impl detail.

## [1.7.0a1] - 2023-02-14
### Added
- Support for the new select menu types to `yuyo.to_builder`.
- `ActionRowExecutor.add_channel_select` for adding channel select menus to an action row.
- `ActionRowExecutor.add_select_menu` for adding the other new select menu types to an action row.
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
- `ActionRowExecutor.add_button` now takes all the button's options as arguments.
  This also now returns the action row and adds the button to the row immediately (without
  any calls to `add_to_parent`).
- Renamed the old `ActionRowExecutor.add_select_menu` to `ActionRowExecutor.add_text_select`
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
- Helper functions for converting some Hikrai modals to builder objects in [yuyo.to_builder][].
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
- [yuyo.components.AbstractComponentExecutor][], `yuyo.components.ChildActionRowExecutor`,
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
  [hikari.RESTBotAware][hikari.traits.RESTBotAware] in
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
- [yuyo.components.BaseContext.respond][] trying to edit in the initial response instead
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
- `WaitForExecutor` now has better semantics/behaviour around being called when it's inactive:
    * Timeouts are now handled better meaning that a wait for executor timeout will mark it to be de-registered.
    * Execute calls to an executor that hasn't been waited for yet now return a not active message.

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

[Unreleased]: https://github.com/FasterSpeeding/Yuyo/compare/v1.14.2...HEAD
[1.14.2]: https://github.com/FasterSpeeding/Yuyo/compare/v1.14.1...v1.14.2
[1.14.1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.14.0...v1.14.1
[1.14.0]: https://github.com/FasterSpeeding/Yuyo/compare/v1.13.0a1...v1.14.0
[1.13.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.12.0a1...v1.13.0a1
[1.12.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.11.2a1...v1.12.0a1
[1.11.2a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.11.1a1...v1.11.2a1
[1.11.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.11.0a1...v1.11.1a1
[1.11.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.10.1a1...v1.11.0a1
[1.10.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.10.0a1...v1.10.1a1
[1.10.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.9.1a1...v1.10.0a1
[1.9.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.9.0a1...v1.9.1a1
[1.9.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.8.0a1.post1...v1.9.0a1
[1.8.0a1.post1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.8.0a1...v1.8.0a1.post1
[1.8.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.7.0a1...v1.8.0a1
[1.7.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.6.1a1...v1.7.0a1
[1.6.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.6.0a1...v1.6.1a1
[1.6.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.5.0a1...v1.6.0a1
[1.5.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.4.0a1.post1...v1.5.0a1
[1.4.0a1.post1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.4.0a1...v1.4.0a1.post1
[1.4.0a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.3.1a1...v1.4.0a1
[1.3.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.2.1a1...v1.3.1a1
[1.2.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.6a1...v1.2.1a1
[1.1.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.6a1...v1.1.1a1
[1.0.6a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.5a1.post1...v1.0.6a1
[1.0.5a1.post1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.5a1...v1.0.5a1.post1
[1.0.5a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.4a1...v1.0.5a1
[1.0.4a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.3a1...v1.0.4a1
[1.0.3a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.2a1...v1.0.3a1
[1.0.2a1]: https://github.com/FasterSpeeding/Yuyo/compare/v1.0.1a1...v1.0.2a1
[1.0.1a1]: https://github.com/FasterSpeeding/Yuyo/compare/0.0.2...v1.0.1a1
