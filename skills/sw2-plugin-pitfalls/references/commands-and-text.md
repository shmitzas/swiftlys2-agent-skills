# Commands, permissions and text

Rules for commands, client-command hooks, permissions and translated text. SwiftlyS2-Skills covers the API: [commands
and permissions][sws2-commands], [localization][sws2-localization] and the [text surfaces][sws2-center-html]. Menus are
in SwiftlyS2-Skills' [`sws2-menus`][sws2-menus]; their click threading is in
[threads-and-scheduler.md](threads-and-scheduler.md#move-classic-menu-clicks-to-the-game-thread).

## Commands

### Hook engine commands instead of registering their names

**Symptom:** a plugin that registers an engine command such as `jointeam` with `registerRaw: true` breaks it. Before
v1.5.1 the registration replaced the engine's command, so every branch of a client-command hook that returned
`Continue` reached the plugin's handler and the engine's action never ran: players could not join Spectator. Since
v1.5.1 the registration is refused with
`Cannot register command "<name>": a command with this name already exists in the engine`, and the plugin's handler
never runs.

**Cause:** native command registration checks for an existing engine command since v1.5.1, and refuses the name.

**Fix:** intercept the command with `HookClientCommand`, filter to it, and either perform the action yourself and
return `Stop`, or return `Continue` and let the engine handle it.

**Evidence:** [`manager.cpp` L195-L224][src-native-register]; refused since v1.5.1, commit
[`23d9257`][commit-cmd-refuse]. The replaced command before v1.5.1: observed in production, 2026-07. The refusal since
v1.5.1: inferred from source, not observed.

### Filter a client-command hook to its own command first

**Symptom:** some players cannot type any command or chat line, and nothing is logged.

**Cause:** a client-command hook sees every console command a client sends, `say` and `say_team` included. For chat it
runs before chat commands and chat hooks, so a `Stop` or `CancelOriginal` returned for the wrong command drops the line
for every later stage and every other plugin.

**Fix:** make the first statement of the handler parse the command token and return `Continue` for any other command.

**Evidence:** [`manager.cpp` L370-L413][src-native-dispatch] and [L175-L183][src-native-handleclient]; [client command
hooks][docs-client-command-hooks]; SwiftlyS2-Skills [intercepting client commands][sws2-intercept]. Observed in
production, 2026-07.

### Read key binds from the user command, not a client-command hook

**Symptom:** a client-command hook meant to catch `+attack2`, `+zoom` or another bound action never fires.

**Cause:** key binds set button bits in the user command. They are not sent to the server as console commands.

**Fix:** read `KeyKind` keys from `OnClientKeyStateChanged`: `+attack2` arrives as `Mouse2`. Use
`Core.GameHooks.Movement.RunCommand.Pre` for other buttons, such as zoom, or to clear one: clear it in
`ctx.Params.UserCmd.ButtonState` and in every step of `CSGOUserCmd.Base.SubtickMoves`, each of which carries its own
`Button`. Whether this stops the action has not been confirmed. The hook runs for every command of every player, so
read each wrapper property once into a local.

**Evidence:** [`manager.cpp` L329-L341][src-native-clienthook], [client command hooks][docs-client-command-hooks];
[`GameKeyKind.cs` L206-L231][src-tokeykind], [`IRunCommand.cs` L6-L35][src-runcommand], [`IUserCmd.cs`
L13-L15][src-usercmd], [`CBaseUserCmdPB.cs` L25][src-gen-subtickmoves] and [`CSubtickMoveStep.cs`
L11][src-gen-subtickbutton]; [game hooks][docs-game-hooks], [`KeyKind` values][docs-keykind]. Inferred from source, not
observed. The never-matching hook for `+attack2` and `+zoom` was found in a code review in 2026-10, not seen failing on
a server.

### Give each command and alias a name no other plugin uses

**Symptom:** a command answers twice, or a plugin's alias works on one server and does nothing on another that runs a
second plugin with the same alias.

**Cause:** when two plugins register the same command name, both handlers join one dispatch list and both run. An alias
name that another plugin or the engine already registered is refused natively, and `RegisterCommandAlias` returns
without an error.

**Fix:** prefix command names with the plugin's own scope and avoid one- or two-letter aliases. At startup, log the
command and alias names that `Core.Command.IsCommandRegistered` already reports before registering them. It knows the
names registered through SwiftlyS2, not engine commands.

**Evidence:** [`CommandDispatcher.cs` L165-L176][src-dispatch-register], [`CommandService.cs`
L47-L70][src-cmdsvc-alias], [`manager.cpp` L195-L214 and L288-L306][src-native-alias], [L80-L95][src-native-resolve]
and [L278-L286][src-native-isregistered]. Inferred from source, not observed.

### Check the caller's pawn before `FindTargettedPlayers`

**Symptom:** a targeting command finds nobody when the caller is still choosing a team or otherwise has no pawn, which
reads as "player not found".

**Cause:** the search drops every candidate when the searching player has no valid pawn, and it only considers players
that have one.

**Fix:** refuse a pawnless caller with its own message, or resolve targets from `GetAllPlayers` for actions that need
no pawn. For destructive actions, refuse an ambiguous name instead of passing `NoMultipleTargets`, which takes the
first match ([framework guarantees][sws2-guarantees]).

**Evidence:** [`PlayerManagerService.cs` L108-L134 and L189-L225][src-pms-find]. Inferred from source, not observed.

## Permissions

### Grant everything with `*` and a subtree with `prefix.*`

**Symptom:** since v1.4.14, a permission group configured as `.*` grants nothing. Before v1.4.14 the same group matched
every permission string, including tier names a plugin checked to tell customers from staff.

**Cause:** v1.4.14 changed wildcard matching. `prefix.*` matches `prefix` and `prefix.<anything>`; with an empty
prefix, `.*` matches only names that start with a dot. `*` alone matches everything. A trailing `*` without the dot, as
in `admin*`, drops one more character than written and matches `admi...`.

**Fix:** use `*` for everything and `prefix.*` for a subtree. Never use a permission check as a negative test such as
"only a donator": every `*` holder passes it. Test the highest tier first and return early.

**Evidence:** [`PermissionManager.cs` L127-L146][src-permissions]; changed in v1.4.14, commit [`48bfce2`][commit-perm].
The old matching: observed in production, 2026-09. The current matching: inferred from source, not observed.

## Translations and text

### Ship `en.jsonc`, and keep each translation file parseable

**Symptom:** the plugin does not load. The log shows `Failed to load plugin` with
`English primary translation file not found.`, `No translation files found.` or a `JsonException`.

**Cause:** when `resources/translations` exists, SwiftlyS2 reads each `.jsonc` file in it as a flat object of strings
while it creates the plugin's core: before the plugin's constructor runs, and outside the `try` around `Load`. A file
that does not parse, a folder with no `.jsonc` file, or a missing `en.jsonc` throws there. The [translation file
layout][docs-translation-layout] page asks for at least one file; the source requires `en.jsonc`, as SwiftlyS2-Skills'
[localization page][sws2-localization] says.

**Fix:** ship `en.jsonc`, keep every value a string, and check before a release that each file parses the way
SwiftlyS2 reads it, with comments and trailing commas allowed. A plugin without translations ships no
`resources/translations` folder.

**Evidence:** [`TranslationFactory.cs` L20-L49][src-translation-factory], [`TranslationService.cs`
L15-L60][src-translation-service], [`SwiftlyCore.cs` L208][src-core-translation], [`PluginManager.cs`
L297-L318][src-pm-startup-catch] and [L400-L428][src-pm-core-first]; [translation file
layout][docs-translation-layout]. Inferred from source, not observed.

### Detect a missing translation by its language prefix

**Symptom:** players see `en.hud.title` or `de.state.warmup`, and a fallback from one localizer to another never runs.

**Cause:** a missing key returns `"<language>.<key>"`, not the key, and `ILocalizer` has no `TryGet`. A fallback that
compares the result with the key never sees the miss.

**Fix:**

```csharp
static bool IsMissing(string? text, string key) =>
    string.IsNullOrEmpty(text) || text == key || text.EndsWith('.' + key, StringComparison.Ordinal);
```

**Evidence:** [`Localizer.cs` L22-L29][src-localizer]; [missing keys and fallback][docs-missing-keys]. Observed in
production, 2026-09.

### Don't expect a custom language file to reach players

**Symptom:** text in a custom language file shows through `Core.Localizer`, but `GetPlayerLocalizer` gives players
English.

**Cause:** with `UsePlayerLanguage` on, `GetPlayerLocalizer` uses the language the player's client reports, and clients
only report the codes the translations page lists.

**Fix:** use `Core.Localizer` for output that follows the server language, and keep `en.jsonc` complete as the
fallback.

**Evidence:** [`TranslationService.cs` L45-L54][src-player-localizer]; [translation file
layout][docs-translation-layout]. Observed in production, 2026-09.

### Keep bracket colours to chat strings

**Symptom:** `[red]` shows up literally in centre text, alerts or menu labels, or a translated string shows stray
control characters there.

**Cause:** the native message path converts colour tokens only for chat and end-of-turn chat. Centre text and alerts
pass the text through, and menus render HTML. Translations have their tokens converted when the file loads, whatever
surface they end up on ([localization][sws2-localization]).

**Fix:** keep one key per surface, as SwiftlyS2-Skills' [localization page][sws2-localization] advises: bracket tokens
for chat, HTML for centre HTML and menus, plain text elsewhere.

**Evidence:** [`player.cpp` L70-L100][src-native-textmsg], [`TranslationFactory.cs` L39][src-translation-colored];
SwiftlyS2-Skills [text surfaces][sws2-center-html]. Observed in production, 2026-11.

[docs-client-command-hooks]: https://swiftlys2.net/docs/development/commands#client-command-hooks
[docs-game-hooks]: https://swiftlys2.net/docs/development/native-functions-and-hooks#higher-level-alternative-game-hooks
[docs-keykind]: https://swiftlys2.net/docs/development/core-events#clientkind-and-keykind
[docs-missing-keys]: https://swiftlys2.net/docs/development/translations#missing-keys-and-fallback
[docs-translation-layout]: https://swiftlys2.net/docs/development/translations#translation-file-layout
[sws2-commands]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/commands-permissions.md
[sws2-intercept]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/commands-permissions.md#intercepting-client-commands
[sws2-guarantees]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md#guarantees
[sws2-localization]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-text-styling/references/localization.md
[sws2-center-html]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-text-styling/references/center-html.md#select-the-surface
[sws2-menus]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/SKILL.md
[commit-cmd-refuse]: https://github.com/swiftly-solution/swiftlys2/commit/23d92571d1e91e7a3ca5181cf1732364c3bb583b
[commit-perm]: https://github.com/swiftly-solution/swiftlys2/commit/48bfce2097382276db8ec1aaaee2dba833f549aa
[src-native-register]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/commands/manager.cpp#L195-L224
[src-native-handleclient]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/commands/manager.cpp#L175-L183
[src-native-clienthook]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/commands/manager.cpp#L329-L341
[src-native-dispatch]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/commands/manager.cpp#L370-L413
[src-native-alias]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/commands/manager.cpp#L195-L306
[src-native-resolve]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/commands/manager.cpp#L80-L95
[src-native-isregistered]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/commands/manager.cpp#L278-L286
[src-native-textmsg]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/src/server/players/player.cpp#L70-L100
[src-runcommand]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/GameHooks/HooksCategories/Movement/IRunCommand.cs#L6-L35
[src-usercmd]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/GameHooks/IUserCmd.cs#L13-L15
[src-gen-subtickmoves]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/Protobufs/Interfaces/CBaseUserCmdPB.cs#L25
[src-gen-subtickbutton]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Generated/Protobufs/Interfaces/CSubtickMoveStep.cs#L11
[src-tokeykind]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Misc/GameKeyKind.cs#L206-L231
[src-dispatch-register]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Commands/CommandDispatcher.cs#L165-L176
[src-cmdsvc-alias]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Commands/CommandService.cs#L47-L70
[src-pms-find]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/PlayerManagerService.cs#L108-L225
[src-permissions]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Permissions/PermissionManager.cs#L127-L146
[src-localizer]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Translations/Localizer.cs#L22-L29
[src-player-localizer]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Translations/TranslationService.cs#L45-L54
[src-translation-colored]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Translations/TranslationFactory.cs#L39
[src-translation-factory]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Translations/TranslationFactory.cs#L20-L49
[src-translation-service]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Translations/TranslationService.cs#L15-L60
[src-core-translation]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/SwiftlyCore.cs#L208
[src-pm-startup-catch]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L297-L318
[src-pm-core-first]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L400-L428
