---
name: cs2-panorama-hud
description: >-
  Traps and checks for CS2 Panorama custom HUDs driven from a SwiftlyS2 plugin through CCSCustomHudLayout, beyond
  SwiftlyS2-Skills' sws2-panorama-authoring and the official Custom HUD page: Panorama CSS that compiles but draws
  differently from a browser, SVG icons, labels and dialog variables, per-player class, variable and input-capture
  state across spectating, reconnects and round restarts, keyboard and mouse input routes, mocking a view in HTML
  before porting it, and checking which copy of a layout a client loaded. Use when a task mentions a Panorama layout,
  vxml, vcss or vsvg, a custom HUD, custom_hud_layout or CCSCustomHudLayout, SetHasClassForPlayer or
  SetDialogVariableString, a label showing a {s:token} or literal markup, a HUD missing or wrong for one player or a
  spectator, a HUD unchanged after a Workshop republish, mouse clicks, input capture or keys driving a HUD, an SVG
  icon that does not draw, or porting a web mock-up to Panorama.
---

# CS2 Panorama HUDs from SwiftlyS2

Covers what goes wrong between a Panorama layout that compiles and a custom HUD that draws right for every player. The
basics live elsewhere, and this skill does not repeat them:

- SwiftlyS2-Skills' [`sws2-panorama-authoring`][sws2-panorama]: resource paths, the validator's markup subset, styling
  choices, delivery basics, spawning the entity, writing state, clicks and cleanup. Its `sws2-menus`
  [renderers page][sws2-renderer] draws a `Core.Menu` menu on a HUD.
- The official [Custom HUD][docs-hud] page: the entity's members, every setter and getter, the class-status values and
  the async variants.
- This pack's [`sw2-asset-pipeline`](../sw2-asset-pipeline/SKILL.md): compiling, the Workshop pack list, and which copy
  of a file a client loaded.
- This pack's [`sw2-plugin-pitfalls`](../sw2-plugin-pitfalls/SKILL.md): plugin rules that are not specific to a HUD,
  among them threads, key binds, transmit blocks and player identity.

This skill adds the Panorama CSS and text traps, how per-player state resolves and how long it lives, the input routes
a plugin can see, a mock-first way to design a view, and delivery checks for layouts. [CustomHUD][customhud] is a
complete public implementation built on these rules: a `Core.Menu` renderer and panel host.

Checked against SwiftlyS2 v1.5.2 and CS2 build 2000943 (2026-11-11). Game behaviour is build-scoped, so every rule in
the references says when it was observed in game, or that it is inferred.

Look up declarations through the SwiftlyS2 MCP or [swiftlys2.net][docs], and Panorama CSS properties through the MCP's
`panorama_list` and `panorama_lookup` tools. If the MCP is unreachable, download a fresh copy of
[`llms-full.txt`][docs-llms-full] and search it rather than reading it whole; each docs page in it starts at a line
beginning `## https://swiftlys2.net/docs`. It has no API reference and no Panorama property list, so take declarations
from the SwiftlyS2 source at the tag of the package version your plugin builds with, and properties from
`dump_panorama_css_properties` in the game's console.

## Decide the route

| Task | Go to |
| --- | --- |
| Create the layout entity, write classes and variables, capture input, receive clicks, clean up | [`sws2-panorama-authoring` integration][sws2-integration] and the [Custom HUD][docs-hud] page; capture with the per-player setter only ([why](references/per-player-hud-state.md#release-input-capture-per-slot)) |
| Layout paths, allowed elements and attributes, styling choices | [`sws2-panorama-authoring` authoring][sws2-authoring] |
| Draw a `Core.Menu` menu on a HUD | [`sws2-menus` renderers][sws2-renderer] |
| A sheet that compiles but draws wrong, an icon that does not draw, a label showing `{s:…}` or markup | [panorama-css-and-text.md](references/panorama-css-and-text.md) |
| A HUD missing, stale or showing someone else's state, for one player or a spectator | [per-player-hud-state.md](references/per-player-hud-state.md) |
| Keys, clicks, commands or chat driving a HUD; HUD keys that fight movement | [input.md](references/input.md) |
| A new view or a restyle | [mock-first-workflow.md](references/mock-first-workflow.md) |
| An edit, a new layout or an icon that does not show in game | [delivery-checks.md](references/delivery-checks.md) |
| Compiling Panorama sources, the Workshop pack list | [`sw2-asset-pipeline` compile-and-inspect](../sw2-asset-pipeline/references/compile-and-inspect.md); compile each `.vxml`, `.vcss` and `.svg` the same way as a VMDL there: `resourcecompiler -f -i <content path>` |

## When a HUD looks wrong in game

Work down the list in order; each step rules out the ones below it.

1. Confirm what the client draws: the layout path the plugin sets, and whether a Workshop copy shadows your files
   ([delivery-checks.md](references/delivery-checks.md)).
2. Read the client console. `Failed to load layout` and `did not pass CustomHud validation` are covered in the
   [authoring page][sws2-authoring-verify]; `Unable to parse SVG` and the "Error parsing layout and style files" dialog
   in [panorama-css-and-text.md](references/panorama-css-and-text.md).
3. Inspect the panel in the Panorama debugger: press F6 to open the debugger and pick the panel there; with
   `panorama_toggledebugger_mode 0`, a second F6 inspects the panel under the cursor
   ([details](references/mock-first-workflow.md#5-hand-over-the-in-game-checks)). It shows the panel tree, the rule that
   won each property and the computed value.
4. Check what the server wrote for that player's slot and globally
   ([per-player-hud-state.md](references/per-player-hud-state.md)).
5. Change one thing at a time, and confirm it in game before copying the change to another view.

## Evidence

Each rule in the references ends with its evidence and how it was established:

- *observed in game, YYYY-MM*: seen on clients and recorded in that month; the sighting can be a few days earlier;
- *inferred, not observed*: read from the SwiftlyS2 source, from Valve's files or from the schema, and not yet seen in
  game.

Report the level a rule carries, and never raise it on reasoning alone. A clean `resourcecompiler` run proves syntax
only: it passes selectors CS2 rejects, missing includes, unknown class names and SVG files the client cannot parse.

## Rules

1. Look up every property and value with `panorama_lookup`, and write each web habit in its
   [Panorama form](references/panorama-css-and-text.md#web-habits-and-their-panorama-form): CS2 drops an unknown
   property or value without a message.
2. Keep each sheet rule at
   [30 selectors or fewer](references/panorama-css-and-text.md#keep-each-rule-at-30-selectors-or-fewer): one selector
   the game cannot read loses the whole sheet.
3. Right after spawning an entity, write a
   [global value](references/per-player-hud-state.md#write-a-global-value-for-everything-you-also-write-per-player)
   for every class and variable you also write per player.
4. Before writing the opposite status for a player,
   [clear the class](references/per-player-hud-state.md#clear-a-per-player-class-before-writing-the-opposite-status)
   with `k_eHudPanelClassStatus_Undefined`, and
   [clear a slot](references/per-player-hud-state.md#treat-the-slot-as-the-key-and-clear-it-when-the-player-leaves)
   when its player leaves.
5. Give a HUD that only its owner may see an
   [entity of its own](references/per-player-hud-state.md#give-a-private-hud-one-entity-per-viewer), transmitted to
   that player alone and written with the global setters, except input capture: enable and release it with
   [`SetInputCaptureEnabledForPlayer`](references/per-player-hud-state.md#release-input-capture-per-slot) for the
   viewer's slot, even on a per-viewer entity.
6. [Write or blank](references/panorama-css-and-text.md#write-or-blank-every-dialog-variable-a-layout-shows) every
   `{s:…}` a layout shows, and send dialog variables
   [plain text](references/panorama-css-and-text.md#send-plain-text-into-dialog-variables).
7. Build keyboard input from the [`KeyKind` keys](references/input.md#build-keyboard-input-from-the-keykind-keys), and
   [leave movement keys](references/input.md#leave-movement-keys-to-movement-on-plain-rows) to movement on plain rows.
8. [Publish the addon](references/delivery-checks.md#before-you-publish) before deploying a plugin that names a new
   layout, class or image.

## What an agent can do alone

An agent can write layouts and sheets, check properties, selector counts and ids, compile, and render a browser mock.
It cannot see what only the game decides. Hand the person running the game an explicit list, by view, input mode and
state:

- border colours, glow and shadow strength, squish, wrapping and rounding, scrolling with the wheel and the thumb, SVG
  sharpness, and fonts;
- every state: default, hover, selected, disabled and empty, and the longest text in each language;
- a second client: a spectator, a player who joins while the HUD is up, and a reconnect into the same slot;
- the HUD after a round restart and after a map change;
- that the Workshop download is the build just published.

## References

| Page | Use it for |
| --- | --- |
| [panorama-css-and-text.md](references/panorama-css-and-text.md) | Web CSS habits and their Panorama form; traps in sheets, layout, borders, animation, SVG and labels |
| [per-player-hud-state.md](references/per-player-hud-state.md) | How a client resolves class, variable and capture state; slots, spectators, joins, rebuilds and threads |
| [input.md](references/input.md) | Mouse, key, command and chat routes; the keys SwiftlyS2 reports; movement keys; activity checks; clicks on menu rows |
| [mock-first-workflow.md](references/mock-first-workflow.md) | Mocking a view in HTML within Panorama's subset, porting it, and the in-game check list |
| [delivery-checks.md](references/delivery-checks.md) | Pack folders, deploy order, orphaned files, Workshop shadowing, caching, which copy a client draws |

[docs]: https://swiftlys2.net
[docs-llms-full]: https://swiftlys2.net/llms-full.txt
[docs-hud]: https://swiftlys2.net/docs/development/custom-hud
[sws2-panorama]: https://github.com/btnrv/SwiftlyS2-Skills/tree/main/skills/sws2-panorama-authoring
[sws2-authoring]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-panorama-authoring/references/authoring.md
[sws2-authoring-verify]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-panorama-authoring/references/authoring.md#validator-subset
[sws2-integration]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-panorama-authoring/references/integration.md
[sws2-renderer]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/references/renderers.md#panorama-hud-renderer
[customhud]: https://github.com/shmitzas/CustomHUD
