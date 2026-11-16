# Contracts in a SwiftlyS2 plugin

A contract is anything that a stored row, a file on a server, another plugin, a tool or an operator depends on. A
published plugin runs on servers its author never sees, so a contract change that looks local can break them on their
next update, often without an error. This page lists what counts as a contract, what may change without asking, and
what a request for approval contains.

## What counts

| Contract | In a SwiftlyS2 plugin | What depends on it |
| --- | --- | --- |
| Plugin identity | The `Id` in `[PluginMetadata]`, which names the config folder `configs/plugins/<Id>` and the data folder `data/<Id>`; the plugin folder and DLL name | Each server's config and data files; deploy scripts |
| Config files | File names, section and key names, value types and units, what each default means, clamps | Every operator's existing files: the binder drops keys that match no property ([rule][lr-key-name]) |
| Database | Tables, columns, types, keys, indexes, version tables, migrations | Stored rows, and other servers that share the database ([rule][pe-version]) |
| Persisted keys | JSON fields, cookie and key-value keys, files in the data folder | Stored player data |
| Shared interfaces | Interface keys, contract types and members, events, DTOs, and when and on which thread each member runs | Plugins built against the contract ([keys][si-key], [timing][si-timing]) |
| Commands | Names, aliases, arguments and their order | Operators, key binds, scripts and other plugins that run them |
| Convars | Names, types, defaults and bounds of the convars the plugin creates with `Core.ConVar.Create` or `CreateOrFind` | Operators' cfg files and scripts |
| Menus | The IDs of `Core.Menu` menus, the names of the actions they declare, and the IDs of the renderers the plugin registers | Operators' `configs/menus/menus.jsonc`, which keys binds and forced renderers by them; a forced renderer ID that is no longer registered stops the menu from building |
| Permissions | The permission strings a command or feature checks | Admin groups configured on each server |
| Translation keys | Keys, and the placeholder indices and the argument each one stands for | Translations maintained outside the repo |
| Enums and constants | Values persisted by number, or mirrored in another plugin or tool | Stored rows and the other copies |
| Other formats | Files, logs, webhooks or messages another tool reads | That tool |

**Evidence:**

- Plugin identity: [`PluginManager.cs` L857-L866][src-pm-createcore],
  [`PluginConfigurationService.cs` L26][src-pcs-basepath], [`DataDirectoryService.cs` L29][src-data-dir],
  [`RootDirService.cs` L23-L31][src-rootdir]. Inferred from source, not observed.
- Convars: [`IConVarService.cs` L30-L67][src-convar-create]. Inferred from source, not observed.
- Menus: [`Bootstrap.cs` L75-L79][src-bootstrap-menus], [`MenuConfigFile.cs` L5-L11][src-menu-config-file],
  [`MenuActionId.cs` L3-L15][src-menu-action-id], [`GlobalMenuKeybindSource.cs` L34-L45][src-menu-keybind-source],
  [`MenuKeybindResolver.cs` L55-L70][src-menu-keybind-resolver],
  [`GlobalMenuRendererSource.cs` L12-L29][src-menu-renderer-source] and
  [`MenuBuilder.cs` L127-L135][src-menu-builder]; SwiftlyS2-Skills' [`sws2-menus` ground rules][sws2-menus-rules] and
  [server configuration][sws2-menus-config]. Inferred from source, not observed.

## The rule

- **Allowed without asking:** an addition whose default keeps today's behaviour, such as a new config key whose
  default changes nothing, a new table for a new feature, a new translation key, a new command or a new member on a
  shared interface. List each one in the plan and in the report.
- **Needs the owner's explicit approval:** renaming, retyping, removing, re-keying, re-scoping, splitting or merging
  an existing contract; renumbering a persisted enum; changing what a default means; migrating existing data; or
  replacing a structure because it looks outdated.
- "Cleaner", "more consistent" and "modern" are not grounds. A defect the current structure causes is.
- An approval covers the contracts it names, not others.

In an audit, a changed contract that is not on the approved list is a Blocker, however good the change.

## What an approval request contains

A request to change an existing contract stops the work on that contract and gives the owner:

1. The change, contract by contract.
2. The defect it fixes: `path:line` and the scenario that fails today.
3. The alternative that keeps the current structure, and why it does not fix the defect.
4. The blast radius: every consumer found by searching the plugin, its docs and the other plugins at hand, and the
   consumers nobody can search, such as servers, stored data and operators' files.
5. The migration and compatibility plan, built from the patterns below.

Work that does not depend on the answer goes on meanwhile.

## Keep existing servers working

| Change | Compatibility plan |
| --- | --- |
| Rename a config key | Keep the stored name with `[ConfigurationKeyName]` ([rule][lr-key-name]) |
| Change a shared-interface member, or when or on which thread it runs | Publish a new versioned key and serve the old one through an adapter while consumers move ([keys][si-key], [timing][si-timing]) |
| Move a persisted key to a new scope | Merge the old and new values, never copy one over the other ([rule][pe-scope]) |
| Change a table | Add a migration. Never edit one that has run: databases that recorded it skip it ([version tables][pe-version], [repairs][pe-guard]) |
| Rename a command | Keep the old name as an alias for a release, if no other plugin uses it ([names][ct-names]) |
| Rename a permission or a translation key | Accept or ship the old one next to the new one for a release |

[lr-key-name]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#keep-the-stored-key-name-when-renaming-a-setting
[pe-version]: ../../sw2-plugin-pitfalls/references/persistence.md#give-each-plugin-and-each-table-prefix-its-own-version-table
[pe-guard]: ../../sw2-plugin-pitfalls/references/persistence.md#guard-each-object-in-a-multi-object-migration
[pe-scope]: ../../sw2-plugin-pitfalls/references/persistence.md#scope-earned-state-to-the-server-when-servers-share-a-store
[si-key]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#add-a-key-for-a-breaking-contract-change
[si-timing]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#treat-timing-and-thread-changes-as-breaking
[ct-names]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#give-each-command-and-alias-a-name-no-other-plugin-uses
[src-pm-createcore]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L857-L866
[src-pcs-basepath]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Services/PluginConfigurationService.cs#L26
[src-data-dir]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Services/DataDirectoryService.cs#L29
[src-rootdir]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Services/RootDirService.cs#L23-L31
[src-convar-create]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/Convars/IConVarService.cs#L30-L67
[src-bootstrap-menus]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Bootstrap.cs#L75-L79
[src-menu-config-file]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menu/Config/MenuConfigFile.cs#L5-L11
[src-menu-action-id]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/Menu/Input/MenuActionId.cs#L3-L15
[src-menu-keybind-source]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menu/Config/GlobalMenuKeybindSource.cs#L34-L45
[src-menu-keybind-resolver]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menu/MenuKeybindResolver.cs#L55-L70
[src-menu-renderer-source]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menu/Config/GlobalMenuRendererSource.cs#L12-L29
[src-menu-builder]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menu/MenuBuilder.cs#L127-L135
[sws2-menus-rules]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/SKILL.md#ground-rules-for-coremenu
[sws2-menus-config]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/references/menu-system.md#server-configuration
