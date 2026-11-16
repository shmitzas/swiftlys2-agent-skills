# Mock a HUD view, then port it

How to design a custom HUD view as an HTML mock that uses only what Panorama can draw, port it to a layout and a sheet,
and hand the result to someone who can check it in game. A mock settles hierarchy, colour and content; only the game
settles layout. The rules this page refers to are in [panorama-css-and-text.md](panorama-css-and-text.md).

## 1. List the data and the states

1. Name the source of every element: the API member, menu row, config value or event that fills it. Leave out an element
   with nothing behind it rather than filling it with sample data: a view designed around invented data has nothing to
   draw against real data.
2. List each state the view has: default, hover, selected, disabled and empty; with and without each optional part; the
   longest text in every language the server ships; every input mode that reaches it, such as mouse, keys and numbers.
3. Note what each state needs from the server: a class on a panel, a dialog variable, or a part that collapses.

## 2. Mock within Panorama's subset

1. Build the mock on a 1920 × 1080 stage scaled to fit the window, and size everything in `px` for that stage.
   Panorama sizes in `px` against a 1080-pixel-tall screen and scales with the screen's height (inferred from
   production layouts, not measured).
2. Use only Panorama's primitives, through these stand-ins:

   | Panorama | Browser stand-in | What the stand-in hides |
   | --- | --- | --- |
   | A `Panel` | A `div` with `width` and `height` set to `fit-content` | An unstyled `div` fills its parent; a `Panel` fits its children on both axes |
   | `flow-children: down` or `right` | `display: flex`, `flex-direction: column` or `row`, no wrapping | Squish: Panorama shrinks children that overflow until they fit; a browser lets them overlap or overflow |
   | `flow-children: right-wrap` | `flex-wrap: wrap` | Rounding that wraps an exactly full line |
   | `flow-children: none` | A one-cell grid with every child placed in that cell | Nothing known |
   | `fill-parent-flow( w )` | `flex: w 1 0` | Nothing known |
   | `horizontal-align`, `vertical-align` | `align-self` across the flow, and nothing along it | Auto margins move items along the flow in a browser; Panorama cannot |
   | `gradient( linear, … )` | `linear-gradient( … )` | Nothing known |
   | `box-shadow: colour x y blur spread` | `box-shadow: x y blur spread colour` | The game draws glow and shadow much stronger |
   | One border colour per panel | The same: never give sides different colours | A browser would draw them |
   | `ui-scale: N%` | `zoom: N%` | Rounding at each scale step |
   | `@define name: value;` | The value written out | Nothing known |
   | `url( "s2r://panorama/images/…vsvg" )` | The source `.svg` file | The game rasterises an SVG once, at its declared size |
   | `Stratum2` | A condensed open-licence face, sizes multiplied by 0.9 | Real text widths, glyph coverage and bold |
   | `{s:name}` | The longest real text in each language | A variable the server never writes shows its token in game |

3. Use the game's look. Stratum2 ships as `stratum2.uifont` in the game's `panorama/fonts` folder, which a browser
   cannot load. A production mock bound a condensed face to the Stratum2 names and scaled its sizes by 0.9, the factor
   the game's own `fonts.conf` applies when Stratum2 falls back to Arial. The file and the factor are read from the
   game's files on build 2000943, first recorded 2026-10; inferred, not observed.
4. When the look is open, render three to five options in this subset and let whoever owns the HUD pick one before you
   port anything.

## 3. Measure

1. Write a width budget for every fixed-column line and every row of parts, such as `3 x 146 + 2 x 6 = 450 of 456`, and
   keep wrapping lines at least 6 px short of their container.
2. Measure the longest text of each label at its size in every language, against the width the layout gives it.
3. Compare the mock with the chosen option by measurement, not by eye.

## 4. Port to the layout and the sheet

1. Map each box of the mock to a `Panel`, `Label`, `Image` or `Button`, with only the attributes the custom HUD
   validator allows ([validator subset][sws2-subset]). Make every clickable box a `Button`.
2. Give an `id` to every panel the server writes, and put each text in a `{s:name}` on the Label that shows it.
3. Turn each state from step 1 into a class on the panel nearest the change, and ship optional parts collapsed. Draw
   pictures as a `background-image` on a class: the server can switch a class, not an `Image`'s `src`.
4. Write each web habit in its Panorama form ([table](panorama-css-and-text.md#web-habits-and-their-panorama-form)),
   look up every property with the MCP's `panorama_lookup`, and keep each rule at 30 selectors or fewer.
5. Compile each `.vxml`, `.vcss` and `.svg` the same way as a VMDL in
   [compile-and-inspect.md](../../sw2-asset-pipeline/references/compile-and-inspect.md#compile):
   `resourcecompiler -f -i <content path>`. A clean run proves syntax only: the compiler passes selectors, includes,
   class names and SVG files that the client rejects.

## 5. Hand over the in-game checks

Give the person running the game a list by view, input mode and state, never just "test it":

| What the mock cannot show | What to check in game |
| --- | --- |
| Border colours | Each bordered panel, in every state |
| Glow and shadow strength | Thin bars, and shadows on translucent panels |
| Squish | The longest text in each language, at the smallest scale step |
| Wrapping and rounding | Every fixed-column line, at each scale step |
| Scrolling | The wheel and the thumb, and a new list opening at its top |
| SVG sharpness | Each icon at its largest size |
| Fonts | Text widths, special characters such as `›` and `×`, and bold |
| Per-player state | A spectator, a player who joins while the HUD is up, and a reconnect into the same slot ([per-player-hud-state.md](per-player-hud-state.md)) |

Ask for the Panorama debugger on anything that looks wrong: in game, press F6 to open the debugger and pick the panel
there. The game's own config sets F6 to open and close it ([gameinfo][gameinfo-f6]); with
`panorama_toggledebugger_mode 0`, a second F6 inspects the panel under the cursor ([convar][cv-toggledebugger]). It
shows the panel tree, the rule that won each property and the computed value. `dump_panorama_css_properties` in the
console lists every property the running build accepts ([command][cv-dump]).

[sws2-subset]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-panorama-authoring/references/authoring.md#validator-subset
[gameinfo-f6]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/game/csgo/gameinfo.gi#L173-L175
[cv-toggledebugger]: https://swiftlys2.net/convars-viewer/cs2/panorama/panorama_toggledebugger_mode
[cv-dump]: https://swiftlys2.net/convars-viewer/cs2/panorama/dump_panorama_css_properties
