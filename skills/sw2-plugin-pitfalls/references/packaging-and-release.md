# Packaging and release

Rules for building, packaging and publishing a plugin. SwiftlyS2-Skills' [template and distribution][sws2-layout]
covers the layout of the zip, and contract DLLs are in
[dependencies-and-contracts.md](dependencies-and-contracts.md#shipping-the-contract).

## Versions

### Build against the oldest SwiftlyS2 you support, and declare it

**Symptom:** a plugin that builds cleanly fails to load on a server with `MissingMethodException: Method not found`,
often right after replacing an obsolete member with the one its warning names.

**Cause:** a plugin compiles against the `SwiftlyS2.CS2` package and runs against the SwiftlyS2 the server has
installed: the template excludes the package's runtime assets, so the plugin ships no copy. `Version="*"` resolves to
the newest stable release at build time and `*-*` to the newest prerelease. A member the server's SwiftlyS2 lacks
throws when the runtime compiles the method that calls it.

**Fix:** pin `SwiftlyS2.CS2` to the oldest SwiftlyS2 version you support, and set `MinimumAPIVersion` in
`[PluginMetadata]` to the same version. SwiftlyS2 then refuses to load the plugin on an older server and names both
versions, instead of failing part-way through `Load`. Before adopting the replacement an obsolete warning suggests,
check that it exists in that version.

**Evidence:** template [`PluginId.csproj` L21][src-template-package]; [`PluginMetadata.cs` L15][src-metadata-minapi],
[`PluginManager.cs` L364-L396][src-pm-minapi]; NuGet's [floating versions][nuget-floating]. Observed in production,
2026-08.

## Building and packaging

### Publish a release from a clean output folder

**Symptom:** a release zip carries files the project no longer produces, such as a removed translation or a contract
DLL that now belongs under `resources/exports`, and a warning count taken from the same tree misses warnings.

**Cause:** `dotnet publish` adds and overwrites files in the publish folder but never deletes any, and the template
zips everything under `build/publish/`. On an up-to-date tree it also skips compilation, so no compiler warning is
reported again.

**Fix:** delete `build/` and `obj/` before a release build, or build releases in CI from a clean checkout. Run
`dotnet clean -c Release` before counting compiler warnings, since `dotnet clean` alone cleans the Debug build, and
`dotnet restore --force` before counting NuGet warnings.

**Evidence:** template [`PluginId.csproj` L11-L12][src-template-paths] and [L34-L40][src-template-zip]. Reproduced in a
test.

### Build, don't pack, a project with `GeneratePackageOnBuild`

**Symptom:** on a clean CI runner, `dotnet pack` of a contract project fails with
`NU5026: The file '...dll' to be packed was not found on disk` without compiling anything. Locally the same command
works.

**Cause:** with `GeneratePackageOnBuild=true`, NuGet's pack targets do not depend on `Build`, because the build itself
packs. Locally the DLL from an earlier build is still on disk.

**Fix:** run `dotnet build -c Release`, which produces the package as part of the build.

**Evidence:** NuGet's [`NuGet.Build.Tasks.Pack.targets` L54-L60][nuget-pack-targets]; Microsoft's [NU5026][ms-nu5026].
Observed in production, 2026-09.

### Match the case of the plugin folder, DLL and project names

**Symptom:** a plugin that loads on a Windows server logs `Plugin entrypoint DLL not found` on a Linux server, or a
Linux CI job cannot find a project file that builds on Windows.

**Cause:** SwiftlyS2 loads `<folder>/<folder>.dll`, and Linux file names are case-sensitive, so it does not find
`MyPlugin/Myplugin.dll` there.

**Fix:** give the plugin folder, the `AssemblyName` and the project file the same name, case included, and build
releases on Linux.

**Evidence:** [`PluginManager.cs` L341-L345][src-pm-entrypoint-check] and [L983-L987][src-pm-entrypoint-path]. The CI
case: observed in production, 2026-07. The plugin folder case: inferred from source, not observed.

## Workshop content

### Keep maps out of content addons that a plugin mounts

**Symptom:** the server logs `Failed to mount world vpk file maps/<map>.vpk, file could not be found`, although the map
is in the published Workshop item.

**Cause:** a plugin that mounts Workshop items as content addons mounts each item's VPK set, so the map's own VPK sits
inside it, and the engine does not mount a world VPK nested in a mounted VPK. `host_workshop_map <id>` loads the item's
files from disk, where the map VPK is a file of its own.

**Fix:** publish each map as its own Workshop item and load it by Workshop ID, outside the list of addons a plugin
mounts. Check what a published item contains as the asset skill's [Workshop packing][asset-pack] describes.

**Evidence:** CS2 behaviour, no SwiftlyS2 code involved. Observed in game, 2026-09.

[sws2-layout]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/layout.md#template-and-distribution
[asset-pack]: ../../sw2-asset-pipeline/references/compile-and-inspect.md#pack-for-the-workshop
[nuget-floating]: https://learn.microsoft.com/en-us/nuget/concepts/dependency-resolution#floating-versions
[ms-nu5026]: https://learn.microsoft.com/en-us/nuget/reference/errors-and-warnings/nu5026
[nuget-pack-targets]: https://github.com/NuGet/NuGet.Client/blob/v10.0.201/src/NuGet.Core/NuGet.Build.Tasks/NuGet.Build.Tasks.Pack.targets#L54-L60
[src-template-package]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/SwiftlyS2.PluginTemplate/templates/PluginId.csproj#L21
[src-template-paths]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/SwiftlyS2.PluginTemplate/templates/PluginId.csproj#L11-L12
[src-template-zip]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/SwiftlyS2.PluginTemplate/templates/PluginId.csproj#L34-L40
[src-metadata-minapi]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Shared/PluginMetadata.cs#L15
[src-pm-entrypoint-check]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L341-L345
[src-pm-minapi]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L364-L396
[src-pm-entrypoint-path]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Plugins/PluginManager.cs#L983-L987
