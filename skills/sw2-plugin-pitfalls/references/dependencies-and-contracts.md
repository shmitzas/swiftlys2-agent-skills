# Shared interfaces and contracts

Rules for publishing and consuming shared interfaces, optional dependencies and contract assemblies. The [shared API
page][docs-shared-api] and SwiftlyS2-Skills' [shared API lifecycle][sws2-shared-lifecycle] cover the basics, and
SwiftlyS2-Skills' [template and distribution][sws2-layout] covers where a contract DLL goes and why replacing one needs
a restart. When the handshake runs relative to `Load` is in
[lifecycle-and-reload.md](lifecycle-and-reload.md#read-shared-interface-fields-after-the-handshake).

A dependency is hard only if every server that runs your plugin, test servers included, also runs its provider. Every
other dependency is soft.

## The handshake

### Let nothing escape a handshake method

**Symptom:** after one plugin loads, reloads or unloads, other plugins stop receiving their shared interfaces. At
server start, the log shows `Hosting failed to start` and no plugin loads.

**Cause:** SwiftlyS2 calls `ConfigureSharedInterface`, `UseSharedInterface` and `OnSharedInterfaceInjected` on every
loaded plugin in loops with no `try` per plugin. At startup the loops run once every plugin has loaded, outside any
`try`, and with `core.ManualLoadPlugins` on also in a `finally` after each plugin; on a load or unload they run in a
`finally`. One exception ends the handshake for every plugin after yours. `GetSharedInterface` throws for a key that
is not registered, `AddSharedInterface` throws for a key that already is, and a missing contract assembly throws when
the method is compiled.

**Fix:** resolve with `TryGetSharedInterface`, even for a provider that every server runs. SwiftlyS2-Skills'
[integration page][sws2-shared-lifecycle] and the official [shared API page][docs-shared-consume] resolve a required
provider with `GetSharedInterface`; use `TryGetSharedInterface` anyway, because an installed provider can still fail
to load or be unloaded, and the throw then ends the handshake for every plugin after yours. Wrap the body of each
handshake method in a `try` that logs. A `try` cannot catch a missing contract in its own method: see the next rule.

**Evidence:** [`PluginManager.cs` L255-L258][src-pm-loadbyname-finally], [L261-L270][src-pm-loadinorder],
[L321-L322][src-pm-startup-rebuild], [L453-L459][src-pm-unload-finally] and [L910-L934][src-pm-rebuild];
[`InterfaceManager.cs` L13-L40][src-im-add-get]. The startup failure: observed in game, 2026-08. The
`GetSharedInterface` and duplicate-key cases: inferred from source, not observed.

### Keep a soft dependency's contract types out of methods that always run

**Symptom:** on a server without the provider, `Hosting failed to start` with
`FileNotFoundException: Could not load file or assembly '<Provider>.Contract'`. The stack points at the
`HasSharedInterface` or `TryGetSharedInterface` line of a method that already catches exactly that exception.

**Cause:** the runtime loads a contract assembly when it compiles a method that names one of its types: a
`TryGetSharedInterface<IFoo>` call, a cast, a call to a method that returns `IFoo`, or a read or write of a field typed
`IFoo?`, even on a branch that never runs. The exception surfaces in the caller, outside the method's own `try`.
Declaring such a field is harmless; touching it is not.

**Fix:** keep the API in an `object?` field and a `bool`, and name the contract type only in methods marked
`[MethodImpl(MethodImplOptions.NoInlining)]` that run after a `HasSharedInterface` probe made inside a `try`. Route
every typed call, event subscription and unsubscription through such a method, and keep contract types out of other
signatures. Search the plugin for the field's name, including `Unload` and log lines: the acquire method is never the
only place that touches it.

```csharp
private object? _foo;          // not IFoo?: touching a typed field loads the contract
private volatile bool _hasFoo; // read this everywhere else

public override void UseSharedInterface(IInterfaceManager im)
{
    _foo = null;
    _hasFoo = false;
    try
    {
        if (im.HasSharedInterface("Foo.Api.v1"))
            AcquireFoo(im);
    }
    catch (Exception ex) // the contract or the provider failed: stay unbound
    {
        Core.Logger.LogWarning(ex, "Foo.Api.v1 is registered but unusable");
    }
}

[MethodImpl(MethodImplOptions.NoInlining)]
private void AcquireFoo(IInterfaceManager im)
{
    im.TryGetSharedInterface<IFoo>("Foo.Api.v1", out var foo);
    _foo = foo;
    _hasFoo = foo is not null;
}
```

**Evidence:** [`PluginManager.cs` L910-L934][src-pm-rebuild], [`InterfaceManager.cs` L25-L51][src-im-get]. Observed in
game, 2026-08.

### Keep optional contract types out of every type in the assembly

**Symptom:** on a server without an optional provider, the plugin fails to load before any of its methods run.

**Cause:** SwiftlyS2 calls `GetTypes()` on the plugin assembly to find the plugin class and its `[SwiftlyInject]`
members, and one type that cannot load without the contract fails the call. A field of a contract struct or enum makes
its declaring type unloadable, and so does the compiler-generated type behind a lambda that captures such a value or an
`async` method that awaits a contract task. Fields typed as contract interfaces or classes do not.

**Fix:** keep contract structs and enums out of fields, captured locals and `async` methods, and convert them to plain
.NET types inside the isolated methods. Load the published plugin with the provider absent before a release.

**Evidence:** [`PluginManager.cs` L850-L855][src-pm-findtype], [`SwiftlyCoreAttributeParser.cs`
L11-L12][src-inject-gettypes]. Reproduced in a test.

### Bind fail-closed and register nothing in the handshake

**Symptom:** a handler fires twice, then three times, after successive plugin reloads. A consumer keeps calling a
provider that was unloaded. A "dependency missing" warning repeats in the log.

**Cause:** on every plugin load, reload and unload, SwiftlyS2 rebuilds the interface registry and runs the three
handshake methods on every loaded plugin again. Anything not idempotent accumulates, and a binder that returns early
when the provider is missing keeps the old reference.

**Fix:** assign the field from `TryGetSharedInterface`, which always writes its `out` value, in both
`UseSharedInterface` and `OnSharedInterfaceInjected`. Subscribe to provider events with `-=` before `+=`. For a soft
dependency, do both inside the isolated method of [the soft-dependency rule][r-soft-dep]. Register game events,
commands and attribute handlers in `Load`, and report a missing provider once, not from the binder.

**Evidence:** [`PluginManager.cs` L255-L258][src-pm-loadbyname-finally], [L453-L459][src-pm-unload-finally] and
[L910-L934][src-pm-rebuild]; [`InterfaceManager.cs` L42-L51][src-im-tryget]; [shared interface
lifecycle][docs-shared-lifecycle]. Observed in production, 2026-09.

### Add a key for a breaking contract change

**Symptom:** after a provider update, consumers built against its previous contract throw `MissingMethodException` or
`TypeLoadException` when they call it.

**Cause:** SwiftlyS2 loads one copy of each export assembly, by name, so every consumer runs against the provider's
current contract, whatever it was compiled against.

**Fix:** add members freely, but never change or remove a published one. For a change that would, publish a new
interface under a new key such as `Foo.Api.v2`, and keep serving the old key through an adapter while consumers move.
Consumers try the newest key first and fall back to older ones.

**Evidence:** [`DependencyResolver.cs` L17-L29][src-depresolver-scan], [`PluginManager.cs`
L526-L536][src-pm-export-load]. Inferred from source, not observed.

## Shipping the contract

### Ship exactly one copy of the contract, in `resources/exports`

**Symptom:** consumers fail with `Could not load file or assembly '<X>.Contract'` and
`Resolving to a collectible assembly is not supported`, the host fails to start, or `TryGetSharedInterface` returns
false while `HasSharedInterface` returns true.

**Cause:** SwiftlyS2 loads every `<plugin>/resources/exports/*.dll` at startup into a context that is never unloaded,
and plugins resolve the contract from there before their own folder. When no export is loaded, because none was
shipped, it failed to load or it was added after startup, a copy next to a plugin DLL loads into that plugin's own
collectible context, as a different type: other plugins cannot resolve it, and the registry, keyed by interface type,
does not match it.

**Fix:** in the provider, build the contract into `resources/exports/`, reference that project with `Private=false`,
remove its sources from the plugin's compile items, and publish the exports folder. In consumers, reference the
contract DLL with `Private=false`, or a contract package with `ExcludeAssets="runtime"`, and ship no copy. Check the
published folder: one copy, under `resources/exports`.

**Evidence:** [`DependencyResolver.cs` L17-L29][src-depresolver-scan]; [`PluginManager.cs` L119-L137][src-pm-resolver],
[L493-L544][src-pm-exports] and [L830-L848][src-pm-loader]; [`InterfaceManager.cs` L42-L51][src-im-tryget];
McMaster.NETCore.Plugins v2.0.0 [`ManagedLoadContext.cs` L97-L102][mcmaster-load]. The load failures: observed in
game, 2026-08. The silent lookup miss: inferred from source, not observed.

### Collect generated exports inside a target

**Symptom:** a release built on a developer machine works, but the CI-built one ships without
`resources/exports/<X>.Contract.dll`. The provider fails to load with `ReflectionTypeLoadException`, and its consumers
lose the interface.

**Cause:** `<Content Include="resources/exports/**/*">` is evaluated before any target runs. On a clean checkout where
the DLL is not committed, it does not exist yet, because the build writes it later, so the glob matches nothing.

**Fix:** gather the exports inside a target that runs before the publish list is computed:

```xml
<Target Name="PublishContractExports" BeforeTargets="ComputeResolvedFilesToPublishList">
  <ItemGroup>
    <_ContractExport Include="$(MSBuildThisFileDirectory)resources/exports/**/*" />
    <ResolvedFileToPublish Include="@(_ContractExport)"
                           RelativePath="resources/exports/%(RecursiveDir)%(Filename)%(Extension)"
                           CopyToPublishDirectory="PreserveNewest" />
  </ItemGroup>
</Target>
```

Test it the way CI builds: delete `resources/exports` and the `bin`, `obj` and `build` folders of the plugin and
contract projects, then publish.

**Evidence:** template [`PluginId.csproj` L24-L28][src-template-content]; Microsoft's [evaluation
phase][ms-msbuild-evaluation]. Observed in production, 2026-09.

### Vendor the contract DLL in each consumer repository

**Symptom:** CI fails with `MSB9008: The referenced project ... does not exist` and `CS0246` on every contract type,
while local builds succeed.

**Cause:** a `ProjectReference` into another repository's contract project resolves only where that repository happens
to be checked out next to it.

**Fix:** commit the provider's contract DLL to the consumer repository and reference it as the previous rules describe.

**Evidence:** build behaviour, no SwiftlyS2 code involved. Observed in production, 2026-09.

## Contract design

### Give consumers state to read, not only events

**Symptom:** a consumer's menu or HUD for one phase never opens, or stays open after the phase has ended.

**Cause:** the consumer depended on one event, and the provider skipped raising it on some paths: a stale player
reference, or one of several exits that tore the phase down without raising it.

**Fix:** in the provider, expose a query for every state it announces by event, and raise the closing event from every
exit. In the consumer, open and close from state changes as well as from events, make both idempotent, undo a claim
when opening fails, and give the UI a deadline.

**Evidence:** plugin API design, no SwiftlyS2 code involved. Observed in production, 2026-09 and 2026-10.

### Treat timing and thread changes as breaking

**Symptom:** after a provider update that changed no signature, a consumer's buttons stay dead or its actions run
twice.

**Cause:** the provider moved an action to the next tick and added paths that reject silently, and the consumer still
assumed the old timing.

**Fix:** version a change of thread, timing or return contract like a signature change. Lead the release notes with the
members it affects and what consumers must change.

**Evidence:** plugin API design, no SwiftlyS2 code involved. Observed in production, 2026-10.

[docs-shared-api]: https://swiftlys2.net/docs/development/shared-api
[docs-shared-consume]: https://swiftlys2.net/docs/development/shared-api#consuming-shared-interfaces
[docs-shared-lifecycle]: https://swiftlys2.net/docs/development/shared-api#shared-interface-lifecycle
[sws2-shared-lifecycle]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/integration.md#shared-api-lifecycle
[sws2-layout]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/layout.md#template-and-distribution
[ms-msbuild-evaluation]: https://learn.microsoft.com/en-us/visualstudio/msbuild/build-process-overview#evaluation-phase
[mcmaster-load]: https://github.com/natemcmaster/DotNetCorePlugins/blob/v2.0.0/src/Plugins/Loader/ManagedLoadContext.cs#L97-L102
[r-soft-dep]: #keep-a-soft-dependencys-contract-types-out-of-methods-that-always-run
[src-pm-resolver]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L119-L137
[src-pm-loadbyname-finally]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L255-L258
[src-pm-loadinorder]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L261-L270
[src-pm-startup-rebuild]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L321-L322
[src-pm-unload-finally]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L453-L459
[src-pm-exports]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L493-L544
[src-pm-export-load]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L526-L536
[src-pm-loader]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L830-L848
[src-pm-findtype]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L850-L855
[src-pm-rebuild]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L910-L934
[src-depresolver-scan]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/DependencyResolver.cs#L17-L29
[src-im-add-get]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/InterfaceManager.cs#L13-L40
[src-im-get]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/InterfaceManager.cs#L25-L51
[src-im-tryget]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/InterfaceManager.cs#L42-L51
[src-inject-gettypes]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/AttributeParsers/SwiftlyCoreAttributeParser.cs#L11-L12
[src-template-content]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/SwiftlyS2.PluginTemplate/templates/PluginId.csproj#L24-L28
