# Check that players draw the layout you built

How to make sure a client draws the layouts, sheets and images you just compiled, and what to check when an edit does
not show. Compiling, the Workshop pack list and the general check for shadowed files are in `sw2-asset-pipeline`'s
[compile-and-inspect.md](../../sw2-asset-pipeline/references/compile-and-inspect.md); getting an addon to players is
in SwiftlyS2-Skills' [authoring page][sws2-delivery].

## Before you publish

1. Keep every file in the Panorama folders the Workshop packer includes: `panorama/layout/custom_game`,
   `panorama/styles/custom_game` and `panorama/images/custom_game`
   ([pack list](../../sw2-asset-pipeline/references/compile-and-inspect.md#pack-for-the-workshop)). Valve's map
   scripting notes place custom HUD layouts in `panorama/layout/custom_game` ([Valve][valve-layout-dir]). Use a folder
   of your own inside each, so your paths cannot collide with another addon's.
2. Delete orphans. A compiled file whose source you renamed or deleted stays in the addon's
   `game/csgo_addons/<addon>/panorama/` tree and ships with the next publish. Remove stale copies from
   `game/csgo/panorama/` as well: they never ship, so a layout that still refers to one works on your machine and fails
   for players.
3. Run the checks the compiler skips: every property against the property list, selector counts, include paths, and
   the panel ids and variable names against what the plugin writes
   ([panorama-css-and-text.md](panorama-css-and-text.md)).
4. Publish the addon before you deploy a plugin that names a new layout, class, variable or image. A new layout drew
   nothing until the addon was republished (seen 2026-11), and the server cannot tell: a layout path the client lacks
   raises no error on the server. A change to what the plugin writes, with nothing changed under `panorama/`, needs no
   republish.

## When an edit does not show

1. Confirm which layout the server asks for: the layout path the plugin sets and the configuration the server runs. An
   edit to a file the server does not name never shows.
2. Check which copy the client loaded, as in `sw2-asset-pipeline`'s
   [which copy](../../sw2-asset-pipeline/references/compile-and-inspect.md#check-which-copy-a-client-loaded). A
   subscribed client mounts Steam's download under `steamapps/workshop/content/730/<item id>/`: compare its date with
   your last publish. In a sheet, make the marker a magenta `color` on one class.
3. Search the compiled files for the revision you expect. A `.vcss_c` or `.vsvg_c` file carries its source text, so a
   text search finds it. A `.vxml_c` file is compressed, so a search can miss text that is there (seen 2026-09). A VPK
   whose entries are compressed may hide text the same way (inferred, not observed).
4. Restart the game after replacing files it has already loaded: layout caching lasts for the client session
   ([authoring page][sws2-delivery]). The retail client has no command that reloads layouts: no `panorama_reload`
   exists, and `panorama_reload_animations` is development-only ([convar][cv-reload]).

[sws2-delivery]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-panorama-authoring/references/authoring.md#delivery-and-verification
[valve-layout-dir]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/content/csgo_addons/cs_script_demo/maps/scripts/point_script.d.ts#L1057-L1058
[cv-reload]: https://swiftlys2.net/convars-viewer/cs2/panorama/panorama_reload_animations
