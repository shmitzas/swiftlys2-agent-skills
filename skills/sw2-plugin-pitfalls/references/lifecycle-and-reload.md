# Lifecycle, hot reload and config reload

Rules for plugin load order, hot reload, map identity and live configuration. SwiftlyS2-Skills covers the basics:
[rebuilding player state after a late load][sws2-player-state], the [configuration and shared-interface
phases][sws2-integration] and [options binding][sws2-di]. Model paths read from configuration follow the asset skill's
[precache rule](../../sw2-asset-pipeline/references/delivery-from-swiftlys2.md#precache-and-pin-the-path).

## Load order

### Assign the static `Core` before anything reads it

**Symptom:** the plugin fails to load. The log shows `Failed to load plugin` and a `TargetInvocationException` wrapping
a `NullReferenceException` thrown from the plugin's constructor.

**Cause:** the porting guide's plugin class hides `BasePlugin.Core` behind a `public static new ISwiftlyCore Core` that
`Load` assigns. Anything that reads `Core` before `Load` runs, such as the constructor, a field initializer or a helper
they call, gets that static while it is still null. `BasePlugin` sets its own `Core` in its constructor, from a core
that is complete before the plugin constructor runs.

**Fix:** keep the constructor empty, or use `base.Core` inside it, and assign the static on the first line of `Load`. A
static marked `[SwiftlyInject]` is assigned before the constructor runs ([next
rule](#put-swiftlyinject-only-on-a-static-iswiftlycore-member)).

**Evidence:** [`BasePlugin.cs` L5-L10][src-baseplugin], [`PluginManager.cs` L857-L877][src-pm-instantiate], porting
guide [base structure][docs-porting-base]. The failure: observed in game, 2026-06. Its cause: inferred from source,
not observed.

### Put `[SwiftlyInject]` only on a static `ISwiftlyCore` member

**Symptom:** a field or property marked `[SwiftlyInject]` is still null when the plugin first uses it, or the plugin
fails to load with an `ArgumentException`.

**Cause:** SwiftlyS2 fills only static fields and properties marked `[SwiftlyInject]`, in every type of the plugin
assembly, and fills them with the plugin's `ISwiftlyCore` before the constructor runs. An instance member, such as the
getting-started example's `ICommandService` field, is never assigned. A static member whose type cannot hold the core,
such as a service interface, makes the assignment throw `ArgumentException` while SwiftlyS2 creates the plugin's core,
outside the `try` around `Load`, and the plugin fails to load.

**Fix:** mark only a static `ISwiftlyCore` member, and reach services through it or the constructor's `core`.

**Evidence:** [`SwiftlyCoreAttributeParser.cs` L9-L31][src-inject-parser], called through [`PluginManager.cs`
L857-L870][src-pm-createcore] from [L400-L428][src-pm-loadinternal], ahead of the `try` around `Load`; [injecting
services into the plugin][docs-inject]. Inferred from source, not observed.

### Read shared-interface fields after the handshake

**Symptom:** `Load` reports a dependency as missing although the provider plugin is loaded and working.

**Cause:** at server start every plugin's `Load` runs first. Only after the last one does SwiftlyS2 run
`ConfigureSharedInterface` for all plugins, then `UseSharedInterface`, then `OnSharedInterfaceInjected`; with
`core.ManualLoadPlugins` on, it also runs them after each plugin's `Load`, for the plugins loaded so far. A reload runs
the same handshake after `Load`.

**Fix:** bind in `UseSharedInterface` and `OnSharedInterfaceInjected` and act on the result there or later, following
[the binder rules](dependencies-and-contracts.md#bind-fail-closed-and-register-nothing-in-the-handshake).

**Evidence:** [`PluginManager.cs` L289-L322][src-pm-loadplugins], [L261-L270][src-pm-loadinorder],
[L211-L259][src-pm-loadbyname] and [L910-L934][src-pm-rebuild]; [shared interface lifecycle][docs-shared-lifecycle].
Observed in game, 2026-07.

### Don't rely on `OnAllPluginsLoaded` after a reload

**Symptom:** a check or setup step in `OnAllPluginsLoaded` runs at server start and never again: not after
`sw plugins reload`, `sw plugins load`, an automatic reload, or another plugin loading.

**Cause:** only startup loading calls `OnAllPluginsLoaded`. The load, reload and unload paths rebuild the shared
interfaces and stop there.

**Fix:** put work that has to follow every handshake in `OnSharedInterfaceInjected`, written so that repeating it is
harmless. Keep `OnAllPluginsLoaded` for work that only matters at server start.

**Evidence:** [`PluginManager.cs`][src-pm-notify] calls `NotifyAllPluginsLoaded` only from startup loading (L269 and
L322); the [load-by-name path][src-pm-loadbyname] ends with `RebuildSharedServices` alone. Inferred from source, not
observed.

### Keep game calls out of `Load` and `Unload` during an automatic reload

**Symptom:** `sw plugins reload` from the server console works, but replacing the DLL on disk makes `Load` throw
`This method can only be called from the main thread.`, or makes game-state reads in `Load` and `Unload` misbehave.

**Cause:** with `AutoHotReload` on, the file watcher reloads the plugin from a `Task.Run` continuation, so `Unload()`
and `Load(hotReload: true)` run on a thread-pool thread. Members that check the thread throw there; others, some marked
`[ThreadUnsafe]` among them, race it.

**Fix:** in `Load`, register handlers and build services, and queue game-state work for the next tick when `hotReload`
is true. In `Unload`, release managed state directly, and hand game-side cleanup, such as despawning the plugin's
entities or restoring a convar it changed, to `Core.Scheduler.QueueOrNow`, which exists since v1.5.2. It runs the
action at once when `Core.IsGameThread` is true, and otherwise on the next tick without the plugin's lifecycle token,
so the action still runs after the plugin's scheduler is gone. `DespawnAsync()` and other `…Async` game members, such
as `SetModelAsync()`, queue the same way ([dispatch and lifetime][sws2-threads]). `DespawnAsync()` has run at once on
the game thread, and otherwise queued without the plugin's token, since v1.0.5. Convars have no async setter. On the
game thread all of these run inside `Unload`, and an exception they throw escapes it, so catch inside the cleanup:
`Despawn` throws for an entity that is already gone. Resolve stored handles inside the queued action and despawn them
there, not with a fire-and-forget `DespawnAsync()`, whose fault nothing observes. Work queued in `Unload` with
`Core.Scheduler.NextTick` or `NextWorldUpdate` carries the plugin's token and is cancelled when the core is disposed
([dispatch and lifetime][sws2-threads]); off the game thread, the next tick or world update may run it first.

On a server older than v1.5.2, a call to `QueueOrNow` makes `Unload` throw `MissingMethodException` before any `try`
in it runs, and the plugin is left [indeterminate](#release-only-what-unloading-leaves-behind-and-let-unload-return).
Use it only in a plugin that declares v1.5.2 as its minimum, as [the packaging
rule](packaging-and-release.md#build-against-the-oldest-swiftlys2-you-support-and-declare-it) describes. To support
servers from v1.2.0, write `if (Core.IsGameThread) CleanUp(); else _ = Core.Scheduler.NextTickAsync(CleanUp);`
instead: `NextTickAsync` takes no lifecycle token either.

```csharp
public override void Load(bool hotReload)
{
    RegisterHandlers();
    if (hotReload)
        Core.Scheduler.NextTick(SeedConnectedPlayers); // runs on the game thread
}

public override void Unload()
{
    _configSubscription?.Dispose(); // managed state: any thread
    Core.Scheduler.QueueOrNow(() => // since v1.5.2: now on the game thread, else next tick
    {
        try { DespawnSpawnedProps(); }
        catch (Exception ex) { Core.Logger.LogWarning(ex, "Unload cleanup failed"); }
    });
}
```

**Evidence:** [`PluginManager.cs` L563-L588][src-pm-filechanged], [L664-L687][src-pm-schedulereload] and
[L737-L741][src-pm-delay]; [`NativeBinding.cs` L11-L17][src-nativebinding]; `[ThreadUnsafe]`
[`IPlayer.SwitchTeam`][src-iplayer-switchteam], with no thread check in [`Player.cs` L181-L188][src-player-switchteam]
or [`GameFunctions.cs` L467-L474][src-gamefunctions-switchteam]. Work queued with `NextTick` or `NextWorldUpdate`:
[`PluginContext.cs` L26-L35][src-plugincontext], [`SwiftlyCore.cs` L235-L238][src-core-dispose], [`SchedulerService.cs`
L210-L228][src-sched-dispose], [`SchedulerManager.cs` L70-L91][src-sched-worldupdate-run], [L131-L136][src-sched-swap]
and [L170-L185][src-sched-nexttick-run]. The game-side cleanup: [`ISchedulerService.cs`
L106-L112][src-isched-queueornow], added in v1.5.2 by commit [`8dd85c4`][commit-queueornow]; [`SchedulerService.cs`
L33-L63][src-sched-service-tokens] and [L87-L90][src-sched-service-queueornow], [`SchedulerManager.cs`
L112-L127][src-sched-async-run], [L352-L370][src-sched-nexttickasync] and [L392-L401][src-sched-queueornow],
[`SwiftlyCore.cs` L284][src-core-isgamethread], [`CEntityInstanceImpl.cs` L28-L33][src-entityimpl-throw] and
[L112-L121][src-entityimpl-despawn], [`CBaseModelEntityImpl.cs` L25-L28][src-modelentity-setmodelasync], [`IConVar.cs`
L110-L119][src-iconvar-value]; at older tags, v1.0.5 [`CEntityInstanceImpl.cs` L209-L212][src-v105-despawnasync] and
[`SchedulerManager.cs` L357-L366][src-v105-queueornow], v1.2.0 [`ISwiftlyCore.cs` L203-L206][src-v120-isgamethread] and
[`SchedulerService.cs` L39-L42][src-v120-nexttickasync]. Inferred from source, not observed.

### Read `GlobalVars` once a map is loaded

**Symptom:** the plugin fails to load at server start with `InvalidOperationException: GlobalVars is null.`, yet loads
fine when reloaded mid-map.

**Cause:** `Core.Engine.GlobalVars` throws while no map is loaded. `Core.Engine.Map`, `MaxPlayers`, `CurrentTime`,
`TickCount` and `Core.PlayerManager.MaxPlayers` read it. `Core.Engine` itself is not null then, so a null check on it
guards nothing.

**Fix:** read these in `OnMapLoad`, an event handler or a scheduled callback, and let a later map load retry when the
read throws.

**Evidence:** [`EngineService.cs` L18-L35][src-engine-globalvars], [`PlayerManagerService.cs` L56][src-pms-maxplayers].
Observed in production, 2026-09.

## Unload

### Release only what unloading leaves behind, and let `Unload` return

**Symptom:** after a reload, every command, event handler and timer of the plugin runs twice. `sw plugins reload` and
an automatic reload log no error, only `Reloaded plugin: <name> (unload 0.0 ms, load … ms)`, which a quick, successful
unload also logs; `sw plugins unload` logs `Failed to unload plugin: <name>`, and the plugin keeps running. Separately,
players lose the classic menus that other plugins had open whenever any plugin unloads or reloads.

**Cause:** when a plugin unloads, SwiftlyS2 calls `Unload`, then disposes the plugin's core. The dispose releases what
SwiftlyS2-Skills lists, [commands, aliases and client hooks][sws2-commands-runtime], [event and hook
listeners][sws2-events-handlers], [`Core.Menu` menus and registrations][sws2-menus-rules] and [scheduler
work][sws2-guarantees], and also the plugin's net-message and entity input and output handlers and the native hooks it
made through `Core.Memory`. It runs only if `Unload` returns. An exception that escapes `Unload` skips it and marks the
plugin indeterminate: a reload then loads a new instance beside the old registrations, and a plain unload leaves them
running. `sw plugins reload` and the automatic reload pass `silent`, so nothing logs that exception, and the unload
time is recorded only after `Unload` returns. The classic `Core.MenusAPI` is one instance shared by every plugin, and
the dispose of any plugin closes every open classic menu, for every player.

**Fix:** in `Unload`, release only what the plugin started outside those services, such as [config change
subscriptions](#dispose-change-subscriptions-in-unload), subscriptions to other plugins' events, and its own threads
and tasks, and catch inside `Unload` so that nothing escapes it. Hand game-side cleanup to the game thread as the
[automatic reload rule](#keep-game-calls-out-of-load-and-unload-during-an-automatic-reload) describes. Expect classic
menus to close when another plugin unloads; `Core.Menu` closes only the unloading plugin's menus.

**Evidence:** [`PluginContext.cs` L26-L35][src-plugincontext], [`SwiftlyCore.cs` L235-L238][src-core-dispose],
[`CommandService.cs` L84-L98][src-cmdsvc-hooks] and [L153-L183][src-cmdsvc-dispose], [`EventSubscriber.cs`
L295-L344][src-subscriber-dispose], [`GameEventService.cs` L169-L172][src-gameevent-dispose], [`GameHooksService.cs`
L44-L98][src-gamehooks-dispose], [`NetMessageService.cs` L91-L94][src-netmsg-dispose], [`EntitySystem.cs`
L335-L356][src-entitysystem-dispose], [`MemoryService.cs` L173-L185][src-memory-dispose] and [`UnmanagedFunction.cs`
L97-L101][src-function-dispose], [`MenuService.cs` L73-L86][src-menu-dispose], [`SchedulerService.cs`
L33-L63][src-sched-service-tokens] and [L210-L228][src-sched-dispose], [`SchedulerManager.cs`
L170-L185][src-sched-nexttick-run]; [`PluginManager.cs` L431-L460][src-pm-unload], [L481-L491][src-pm-reload],
[L220-L227][src-pm-loadold], [L325-L333][src-pm-loadinternal-remove] and [L664-L687][src-pm-schedulereload],
[`CoreCommandService.cs` L500-L531][src-corecmd-plugins]; [`SwiftlyCore.cs` L119][src-core-menusapi],
[`MenuManagerAPI.cs` L37][src-menusapi-openmenus] and [L571-L588][src-menusapi-closeall]. Inferred from source, not
observed.

## Maps

### Identify the running map by its Workshop ID

**Symptom:** on Workshop maps, looking the current map up in the plugin's map list finds nothing, and the features
built on it do nothing: a vote offers the map being played, map cooldowns never apply, a reload runs `changelevel` with
a name the server cannot load.

**Cause:** `Core.Engine.Map` is the map file's internal name. It matches neither the Workshop title nor a configured
display name. `Core.Engine.WorkshopId` holds the ID, and is empty or `"0"` on stock maps.

**Fix:** resolve by Workshop ID first and fall back to the name for stock maps:

```csharp
var workshopId = Core.Engine.WorkshopId?.Trim() ?? "";
var current = workshopId is { Length: > 0 } and not "0"
    ? FindMapByWorkshopId(workshopId)
    : FindMapByName(Core.Engine.Map);
```

**Evidence:** [`EngineService.cs` L27-L29][src-engine-map]. Observed in production, 2026-10.

## Config reload

### Read settings through the monitor, not a copy

**Symptom:** editing the plugin's config file changes nothing until the plugin is reloaded, even when a `reloaded` line
is logged.

**Cause:** `reloadOnChange` refreshes `IOptionsMonitor<T>`. `IOptions<T>.Value`, a `CurrentValue` copied into a field
or a constructor, and values extracted during `Load` keep the old settings. The porting guide's configuration example
stores `IOptions<T>.Value`.

**Fix:** read `monitor.CurrentValue` where the value is used, or swap a field in `OnChange` and pass services a
`Func<TConfig>` instead of the object.

**Evidence:** [configuration, complete example][docs-config-example], porting guide [loading
configuration][docs-porting-config]. Observed in production, 2026-09.

### Re-run decisions made in `Load` when the config changes

**Symptom:** switching a feature off, changing a timer interval or renaming a command in the config has no effect until
the plugin reloads. A renamed command answers to both names.

**Cause:** a reload re-binds values. Hooks, timers and commands chosen from the config during `Load` are not re-chosen,
and registering a new command name does not remove the old one.

**Fix:** react in `OnChange`: unhook and hook again, cancel and recreate the timer, `UnregisterCommand(guid)` the old
name before registering the new one. Where that is not worth it, log that the setting needs a plugin reload.

**Evidence:** [`CommandService.cs` L42-L72][src-cmdsvc-register]; SwiftlyS2-Skills [runtime command
registration][sws2-commands-runtime]. Observed in production, 2026-09.

### Never write the watched file from a change callback

**Symptom:** the plugin logs `config reloaded` several times a second and keeps doing so.

**Cause:** writing the config file, or calling `IConfigurationRoot.Reload()`, inside `OnChange` or
`ChangeToken.OnChange` raises the reload token again. `ChangeToken.OnChange` registers the callback again after it
returns, so a re-entrancy flag never sees the next call coming.

**Fix:** seed, migrate and clean the file on explicit load paths only. Keep change callbacks free of file writes.

**Evidence:** Microsoft's [change tokens][ms-change-tokens]. Observed in production, 2026-09.

### Save config files atomically

**Symptom:** right after an operator saves the file, the console prints
`CRITICAL: Unobserved task exception. Aborting.` with `The input does not contain any JSON tokens` at
`LineNumber: 0 | BytePositionInLine: 0`, often next to a successful `reloaded` line. The edit is lost until the next
save.

**Cause:** an editor or upload that truncates the file before writing it lets the file watcher read zero bytes, and the
JSON provider throws on the watcher's callback. SwiftlyS2's handler logs that as critical, marks it observed and keeps
the process running. If the source's `OnLoadException` handler ignores the failure instead, the provider raises the
reload with an empty section and every option falls back to its default.

**Fix:** upload to a temporary file and rename it over the config, or edit with the server stopped. A reload handler
that ignores load exceptions has to refuse an empty result.

**Evidence:** [`Bootstrap.cs` L33-L38][src-bootstrap-unobserved]; .NET's [`FileConfigurationProvider`
L96-L153][dotnet-fileprovider]. The failed read: observed in production, 2026-09. That the process keeps running:
inferred from source, not observed.

### Know which binds replace a default collection

**Symptom:** default list entries appear twice after the first start, or an operator cannot remove a default entry.

**Cause:** `AddSwiftly` installs `SwiftlyOptionsFactory`, which clears a default list or dictionary before binding when
the file has that key. It only does so for options bound with `BindConfiguration`, and for those it binds the section
itself and skips any other `Configure` action registered for the type. Binding through `GetSection(...).Get<T>()`,
`Bind` or `Configure<T>(section)` uses the standard binder, which appends file entries to a non-empty default.

**Fix:** bind with `AddOptions<T>().BindConfiguration(section)` after `AddSwiftly`. Anywhere else, start collections
empty and supply the defaults only when the file is created. Use `PostConfigure` for adjustments after binding.

**Evidence:** [`SwiftlyCoreInjection.cs` L30-L87][src-optfactory-create] and [L119-L147][src-optfactory-clear];
[configuration, complete example][docs-config-example]. The appending binder: reproduced in a test. The skipped
`Configure` actions: inferred from source, not observed.

### Keep the stored key name when renaming a setting

**Symptom:** after an update renames a config property, servers quietly run with its default. The old key stays in the
file and does nothing, and operators keep editing it.

**Cause:** the configuration binder ignores keys that match no property. `InitializeJsonWithModel(name, section)` adds
keys missing from an existing file by default, so the new name appears with its default value.

**Fix:** keep the stored name with `[ConfigurationKeyName("OldName")]` on the renamed property. When behaviour
contradicts a value in the file, search the model for that key before debugging the feature.

**Evidence:** [`PluginConfigurationService.cs` L70-L111][src-pcs-init], [adding missing
keys][docs-config-missing-keys], Microsoft's [`ErrorOnUnknownConfiguration`][ms-binder-unknown]. The ignored key:
observed in production, 2026-09. The inserted default: inferred from source, not observed.

### Don't let an ignored member claim a config key name

**Symptom:** the plugin fails to load with
`InvalidOperationException: The JSON property name for '<Type>.<Name>' collides with another property`, thrown from
`InitializeJsonWithModel`.

**Cause:** SwiftlyS2 serializes the model with a resolver that renames properties from `[ConfigurationKeyName]`.
Properties marked `[JsonIgnore]` still take part in the duplicate-name check, so a bound property renamed to `Skills`
collides with an ignored property called `Skills`. With the default overload the model is serialized on every load, not
only when the file is created.

**Fix:** give the computed or ignored member a name that no configuration key uses.

**Evidence:** [`PluginConfigurationService.cs` L92-L106][src-pcs-serialize]. Observed in production, 2026-10.

### Dispose change subscriptions in `Unload`

**Symptom:** after a few hot reloads, one config edit runs the reload callback once for every earlier plugin instance.

**Cause:** the plugin's configuration manager, with its file watchers, is not disposed when the plugin unloads.
`AddSwiftly` registers it as an existing instance, which the service provider never disposes, and the configuration
service that creates it is not disposable.

**Fix:** keep the `IDisposable` that `OnChange` or `ChangeToken.OnChange` returns and dispose it in `Unload`.

**Evidence:** [`SwiftlyCoreInjection.cs` L193-L199][src-addswiftly-config], [`PluginConfigurationService.cs`
L193-L205][src-pcs-manager], [`PluginContext.cs` L26-L35][src-plugincontext]. Inferred from source, not observed.

[docs-porting-base]: https://swiftlys2.net/docs/guides/porting-from-css#base-structure
[docs-inject]: https://swiftlys2.net/docs/development/getting-started#injecting-services-into-the-plugin
[docs-porting-config]: https://swiftlys2.net/docs/guides/porting-from-css#loading-configuration
[docs-shared-lifecycle]: https://swiftlys2.net/docs/development/shared-api#shared-interface-lifecycle
[docs-config-example]: https://swiftlys2.net/docs/development/configuration#complete-example
[docs-config-missing-keys]: https://swiftlys2.net/docs/development/configuration#adding-missing-keys
[sws2-player-state]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/player-state.md#initialize-and-release-state
[sws2-integration]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/integration.md
[sws2-di]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/dependency-injection.md
[sws2-commands-runtime]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/commands-permissions.md#fixed-and-runtime-registration
[sws2-events-handlers]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/events-hooks.md#fixed-and-dynamic-handlers
[sws2-menus-rules]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/SKILL.md#ground-rules-for-coremenu
[sws2-guarantees]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md#guarantees
[sws2-threads]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-thread-management/references/threads.md
[ms-change-tokens]: https://learn.microsoft.com/en-us/aspnet/core/fundamentals/change-tokens
[ms-binder-unknown]: https://learn.microsoft.com/en-us/dotnet/api/microsoft.extensions.configuration.binderoptions.erroronunknownconfiguration
[dotnet-fileprovider]: https://github.com/dotnet/runtime/blob/v10.0.0/src/libraries/Microsoft.Extensions.Configuration.FileExtensions/src/FileConfigurationProvider.cs#L96-L153
[src-baseplugin]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Plugins/BasePlugin.cs#L5-L10
[src-pm-instantiate]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L857-L877
[src-pm-createcore]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L857-L870
[src-pm-loadinternal]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L400-L428
[src-pm-loadinorder]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L261-L270
[src-inject-parser]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/AttributeParsers/SwiftlyCoreAttributeParser.cs#L9-L31
[src-pm-loadplugins]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L289-L322
[src-pm-rebuild]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L910-L934
[src-pm-notify]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L936-L942
[src-pm-loadbyname]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L211-L259
[src-pm-filechanged]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L563-L588
[src-pm-schedulereload]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L664-L687
[src-pm-delay]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L737-L741
[src-nativebinding]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Natives/NativeBinding.cs#L11-L17
[src-iplayer-switchteam]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/Players/IPlayer.cs#L448-L449
[src-player-switchteam]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/Player.cs#L181-L188
[src-gamefunctions-switchteam]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Natives/GameFunctions.cs#L467-L474
[src-plugincontext]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginContext.cs#L26-L35
[src-sched-nexttick-run]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerManager.cs#L170-L185
[src-sched-swap]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerManager.cs#L131-L136
[src-sched-worldupdate-run]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerManager.cs#L70-L91
[src-sched-async-run]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerManager.cs#L112-L127
[src-sched-nexttickasync]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerManager.cs#L352-L370
[src-sched-queueornow]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerManager.cs#L392-L401
[src-sched-service-tokens]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerService.cs#L33-L63
[src-sched-service-queueornow]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerService.cs#L87-L90
[src-sched-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerService.cs#L210-L228
[src-isched-queueornow]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/Scheduler/ISchedulerService.cs#L106-L112
[commit-queueornow]: https://github.com/swiftly-solution/swiftlys2/commit/8dd85c4e9eeb949a5e0c988990a608cb87265049
[src-v120-isgamethread]: https://github.com/swiftly-solution/swiftlys2/blob/v1.2.0/managed/src/SwiftlyS2.Shared/ISwiftlyCore.cs#L203-L206
[src-v120-nexttickasync]: https://github.com/swiftly-solution/swiftlys2/blob/v1.2.0/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerService.cs#L39-L42
[src-core-isgamethread]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/SwiftlyCore.cs#L284
[src-core-menusapi]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/SwiftlyCore.cs#L119
[src-core-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/SwiftlyCore.cs#L235-L238
[src-entityimpl-throw]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CEntityInstanceImpl.cs#L28-L33
[src-entityimpl-despawn]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CEntityInstanceImpl.cs#L112-L121
[src-v105-despawnasync]: https://github.com/swiftly-solution/swiftlys2/blob/v1.0.5/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CEntityInstanceImpl.cs#L209-L212
[src-v105-queueornow]: https://github.com/swiftly-solution/swiftlys2/blob/v1.0.5/managed/src/SwiftlyS2.Core/Modules/Scheduler/SchedulerManager.cs#L357-L366
[src-modelentity-setmodelasync]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CBaseModelEntityImpl.cs#L25-L28
[src-iconvar-value]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/Modules/Convars/IConVar.cs#L110-L119
[src-cmdsvc-hooks]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Commands/CommandService.cs#L84-L98
[src-cmdsvc-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Commands/CommandService.cs#L153-L183
[src-subscriber-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Events/EventSubscriber.cs#L295-L344
[src-gameevent-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/GameEvents/GameEventService.cs#L169-L172
[src-gamehooks-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/GameHooks/GameHooksService.cs#L44-L98
[src-netmsg-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/NetMessages/NetMessageService.cs#L91-L94
[src-entitysystem-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/EntitySystem/EntitySystem.cs#L335-L356
[src-memory-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Memory/MemoryService.cs#L173-L185
[src-function-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Memory/UnmanagedFunction.cs#L97-L101
[src-menu-dispose]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menu/MenuService.cs#L73-L86
[src-menusapi-openmenus]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menus/MenuManagerAPI.cs#L37
[src-menusapi-closeall]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Menus/MenuManagerAPI.cs#L571-L588
[src-pm-unload]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L431-L460
[src-pm-reload]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L481-L491
[src-pm-loadold]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L220-L227
[src-pm-loadinternal-remove]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L325-L333
[src-corecmd-plugins]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Services/CoreCommandService.cs#L500-L531
[src-engine-globalvars]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Engine/EngineService.cs#L18-L35
[src-engine-map]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Engine/EngineService.cs#L27-L29
[src-pms-maxplayers]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Players/PlayerManagerService.cs#L56
[src-cmdsvc-register]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Commands/CommandService.cs#L42-L72
[src-bootstrap-unobserved]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Bootstrap.cs#L33-L38
[src-optfactory-create]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/SwiftlyCoreInjection.cs#L30-L87
[src-optfactory-clear]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/SwiftlyCoreInjection.cs#L119-L147
[src-addswiftly-config]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/SwiftlyCoreInjection.cs#L193-L199
[src-pcs-init]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Services/PluginConfigurationService.cs#L70-L111
[src-pcs-serialize]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Services/PluginConfigurationService.cs#L92-L106
[src-pcs-manager]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Services/PluginConfigurationService.cs#L193-L205
