# Panorama CSS and text traps

Rules for custom HUD sheets, icons and labels that compile cleanly and then draw wrong, or not at all. The markup
subset, the styling-decision table and the colour-first `box-shadow` are in SwiftlyS2-Skills'
[authoring page][sws2-authoring]; this page adds what that page and a browser preview do not show. Checked against
SwiftlyS2 v1.5.2 and CS2 build 2000943 (2026-11-11).

Each rule gives the symptom, the cause, the fix and the evidence, and says how the rule was established: *observed in
game* in a given month, or *inferred, not observed*. "Valve's sheets" means the 241 stylesheets of build 2000943 as
tracked by [GameTracking-CS2][valve-styles]; the counts below come from a survey of that commit.

## Web habits and their Panorama form

CS2 drops an unknown property, or a value it cannot parse, without a console message (observed in game, 2026-11).
Look up every property you use with the MCP's `panorama_lookup` ([property list][pv-list]), and write the Panorama form
of each web habit:

| Web habit | Panorama form | Evidence |
| --- | --- | --- |
| `display: flex` or `grid`, `justify-content`, `align-items` | `flow-children` on the parent; `horizontal-align` and `vertical-align` on the child work across the flow only; spacing along the flow comes from child order and `fill-parent-flow()` | none of them in the [property list][pv-list]; [`width`][pv-width]; that the aligns work across the flow only is inferred, not observed, recorded 2026-11 |
| Relying on a container's default flow | `flow-children` set on every container that holds several children | [`flow-children`][pv-flow] has no documented default |
| `position: absolute` with `top` and `left` | `position: x y z` on a child of a parent with `flow-children: none`, or alignment plus margins | [`position`][pv-position]; no `top` or `left` in Valve's sheets |
| A negative margin that pulls one sibling over another | `flow-children: none` on the parent ([rule](#overlap-panels-with-flow-children-none-not-negative-margins)) | observed in game, 2026-09 |
| `vw`, `vh`, `em`, `rem`, `calc()` | `px`, `%`, `width-percentage()`, `height-percentage()` | [`width`][pv-width]; none in Valve's sheets |
| `var(--name)` | `@define name: value;` at the top of the sheet, used bare | 478 `@define`, no `var(` in Valve's sheets |
| `linear-gradient()` | `gradient( linear, 0% 0%, 0% 100%, from( #a ), to( #b ) )` | 407 `gradient(`, no `linear-gradient(` in Valve's sheets |
| `hsl()` | `#rrggbbaa`, `rgba()` or `rgb()` | no `hsl(` in Valve's sheets |
| `backdrop-filter: blur()`, `filter: blur()` | `background-blur`, `blur` | [property list][pv-list] |
| `transform: scale()` for a size setting | `ui-scale`, which re-runs layout so text stays sharp; one class per step | [`ui-scale`][pv-ui-scale] |
| `text-shadow: x y blur colour` | `text-shadow: x y blur strength colour` | [`text-shadow`][pv-text-shadow] |
| The `animation` and `transition` shorthands | their longhands ([rule](#keep-animation-longhands-in-the-rule-that-names-the-animation)) | no shorthand in Valve's sheets |
| `@keyframes name` | `@keyframes 'name'` | 261 quoted names, no unquoted one, in Valve's sheets |
| `::before`, `::after`, `:nth-child()`, `[attr]` selectors | a class the server sets, or another panel; `:not()`, `:first-child` and `:last-child` exist | none in Valve's sheets; `:not()` in 218 rules |
| `@media` | none known for custom HUDs: Valve's sheets key off ancestor classes such as `AspectRatio16x9`, which custom HUD layouts are not known to receive | no `@media` in Valve's sheets |
| `//` comments | `/* */` | no `//` comment in Valve's sheets |

## Sheets

### Keep each rule at 30 selectors or fewer

- **Symptom:** no rule in one sheet applies. The game shows an "Error parsing layout and style files" dialog naming the
  sheet and line (`Failed to parse selector`), then another from the layout that included it (`Failed to add include`).
- **Cause:** a selector the parser cannot read loses the whole sheet, and an over-long selector list is one: lists of
  48 and 190 selectors failed. Valve's sheets never put more than 30 selectors, or more than 1,655 characters of
  selectors, in one rule. `resourcecompiler` does not parse selectors, so the build passes.
- **Fix:** split a long list, such as a ladder of `.bar-N` rules or one look shared by many views, into rules of at
  most 30 selectors and about 1,600 characters with the same body.
- **Evidence:** observed in game, 2026-11. The limits of Valve's sheets come from the survey.

### Keep animation longhands in the rule that names the animation

- **Symptom:** a panel rests on its base style and never animates.
- **Cause:** Panorama does not merge `animation-*` longhands across rules the way a browser does. With the duration and
  fill mode in one rule and `animation-name` in another, the animation ran without its timing.
- **Fix:** write `animation-name`, `-duration`, `-timing-function`, `-iteration-count`, `-delay` and `-fill-mode`
  together in every rule that starts an animation. Use the longhands, as Valve's sheets do.
- **Evidence:** observed in game, 2026-09.

### Start animations with a class the server adds

- **Symptom:** an animation runs ahead of or behind the server event it shows, such as a coin still turning after the
  result was announced in chat.
- **Cause:** a CSS animation's clock starts when the client creates the panel, which depends on when the entity reached
  that client, not on the server's timeline. `animation-delay` cannot line the two up.
- **Fix:** put `animation-name` behind a trigger class and have the server add the class when the event happens. Hold a
  pause before the motion on the server, not in `animation-delay`, and set `animation-fill-mode: forwards` to keep the
  last frame. To replay, create a new entity: whether removing and re-adding the class restarts the animation is not
  established.
- **Evidence:** observed in game, 2026-09.

## Layout and sizing

### Give a full-width child a parent with a size

- **Symptom:** a panel or label with `width: 100%` draws nothing.
- **Cause:** panels default to `fit-children` ([`width`][pv-width]). Inside a `fit-children` parent, the child sizes to
  the parent while the parent sizes to its children, and Panorama resolves that loop to zero.
- **Fix:** give the parent or the child a pixel size, or use `fill-parent-flow()` inside a parent that has one.
- **Evidence:** observed in game, 2026-11: a full-width label inside a chip drew nothing.

### Keep padding off a scrolling parent of a full-width child

- **Symptom:** a full-width child runs past its parent's right edge by both paddings: 40 px past a list padded 20 px on
  each side.
- **Cause:** `width: 100%` is a share of the parent's whole width, padding included. The default `overflow: squish`
  shrinks the child back inside the padding; `clip` and `scroll` let it keep that width ([`overflow`][pv-overflow]).
- **Fix:** give the panel `overflow: squish scroll`, or put the padding on a panel inside it.
- **Evidence:** observed in game, 2026-11.

### Give a scrolling panel a pixel height

- **Symptom:** a scrollbar shows, but neither the mouse wheel nor dragging the thumb moves the list.
- **Cause:** the list's height came from `fill-parent-flow()`, directly or as `height: 100%` of a box that fills its
  parent. Every panel seen scrolling in game had a pixel height.
- **Fix:** give the scrolling panel a pixel height and `overflow: squish scroll`. A `max-height` cap keeps what follows
  on screen but has not been seen scrolling. The panel keeps its scroll offset when the server replaces its rows, so a
  new list can open scrolled down; no way to reset the offset has been confirmed in game.
- **Evidence:** observed in game, 2026-11.

### Keep a fixed-column wrapping line short of its container

- **Symptom:** a five-column grid draws four cards and a gap; two 50% cards draw on two lines.
- **Cause:** with `flow-children: right-wrap`, a line that is exactly full wraps its last child once layout and
  `ui-scale` rounding add a fraction of a pixel.
- **Fix:** keep each line at least 6 px short of the container's inner width, and write the budget in the rule's comment
  (`3 x 146 + 2 x 6 = 450 of 456`). Or give each line its own panel that flows `right` without wrapping: its default
  `overflow: squish` absorbs the rounding.
- **Evidence:** the wrap of an exactly full line, and line panels that hold, observed in game, 2026-11; the 6 px slack
  is inferred, not observed.

### Overlap panels with flow-children none, not negative margins

- **Symptom:** a panel meant to sit on top of another sits below it, often outside the visible area.
- **Cause:** in a flowing parent the flow places each child, and a negative margin does not pull a flowed child over its
  sibling as it does in a browser. Negative margins against an alignment anchor do work.
- **Fix:** set `flow-children: none` on the parent: each child lays out at the parent's origin, so same-sized children
  stack. Offset one with margins, or with [`position`][pv-position], which needs a parent that does not flow.
- **Evidence:** observed in game, 2026-09.

## Borders and effects

### Draw one border colour per panel

- **Symptom:** all sides of a panel come out in one colour: an orange left edge drew grey under a grey top hairline, and
  grey sides drew orange under an orange top.
- **Cause:** Panorama keeps each side's width but draws every side in one colour, the top's when the top has one. A
  browser draws each side in its own colour, so a mock never shows this.
- **Fix:** give each panel one border colour, and draw a second colour, such as an accent edge, with a child panel.
- **Evidence:** observed in game, 2026-11.

### Make glow and shadows weaker than the mock

- **Symptom:** a thin bar gets a thick, bright halo; a side panel's drop shadow reads as a heavy smear.
- **Cause:** `box-shadow` draws much stronger in game than in a browser: a 6 px blur round a 2 px bar became a halo. A
  `fill` shadow ([`box-shadow`][pv-box-shadow]) is drawn behind the whole panel, so it also darkens through a
  translucent surface.
- **Fix:** put no `box-shadow` on bars 4 px or thinner, give translucent panels about half the shadow the mock uses, and
  judge the strength in game.
- **Evidence:** observed in game, 2026-11.

### Hide under native panels with the game's ancestor classes

- **Symptom:** a HUD covers the scoreboard, the buy menu, chat or the end-of-match panel.
- **Cause:** custom HUD layouts sit under a window root of their own ([layout][valve-customhuds]), and `z-index` orders
  panels only within one parent ([`z-index`][pv-z-index]), so no value puts a layout under the game's HUD.
- **Fix:** hide or move the layout with descendant selectors on the classes the client sets on an ancestor panel while
  those panels are up: `HUD_TEAMINTRO_VISIBLE`, `HUD_BUYMENU_VISIBLE`, `HUD_SCOREBOARD_VISIBLE`, `HUD_WINPANEL_VISIBLE`,
  `HUD_ENDOFMATCH_VISIBLE`, `HUD_TEAMMENU_VISIBLE` and `HUD_CHAT_VISIBLE` ([Valve][valve-hud-classes]). For example,
  `.HUD_SCOREBOARD_VISIBLE .my-hud { visibility: collapse; }`, the form the game's own HUD sheets use
  ([example][valve-hudrush]).
- **Evidence:** Valve's declarations and sheets at build 2000943; for custom HUD layouts, inferred, not observed.

## Images

### Treat an SVG as unproven until the client draws it

- **Symptom:** an icon never draws, and the client console logs `[Panorama] Unable to parse SVG '<path>.vsvg': ` with
  nothing after the colon, or logs nothing.
- **Cause:** `resourcecompiler` wraps the SVG text without parsing it and reports success; only the client parses it,
  and it accepts less than a browser. In tests, a root with only a `viewBox` drew nothing, and a file with arc commands
  drew only after they were rewritten as cubic curves.
- **Fix:** normalise every export before compiling: `width` and `height` on the root; arcs rewritten as cubic curves;
  one element per line; an `<?xml ?>` prolog; `<ellipse>` or `<path>` instead of `<circle>`; no `fill="none"` on the
  root. Give a colour its alpha with `fill-opacity` or `opacity`, not 8-digit hex. Look at each icon in game.
- **Evidence:** the empty error, the `viewBox`-only root, and a file with arcs that failed with no error and drew once
  they were rewritten, observed in game, 2026-09. The prolog, one element per line, `<ellipse>` and no `fill="none"`
  on the root are inferred, not observed, from a 2026-09 survey of 114 of the game's own SVG icons, which follow those
  forms. The alpha item is inferred, not observed, from a separate survey of 1,169 of the game's SVG files, recorded
  2026-11: none writes 8-digit hex.

### Declare an SVG at about twice the size it draws

- **Symptom:** an icon or emblem is blurry or soft in game, while the same file is sharp in a browser.
- **Cause:** the client rasterises an SVG once, at the `width` and `height` its root declares, with no mip chain, and
  stretches that bitmap to the panel: an emblem declared 32 × 13 and drawn 270 px wide was magnified about eight times.
- **Fix:** declare the root's `width` and `height` at about twice the size you draw: smaller declarations blur, and
  larger ones soften again. Change those, never the `viewBox`, which rescales the artwork. For a 24-unit icon in a
  22 px slot, a declared 24 drew blurry, 48 sharpest, and 64 to 128 softer. CS2 also lists a
  [`background-texture-size`][pv-texture-size] property, but its effect is undocumented and not observed: the declared
  size, at about twice the size drawn, is the measured way to get a sharp icon.
- **Evidence:** the blur observed in game, 2026-09 and 2026-11; the sizes measured in game, 2026-09.
  `background-texture-size` is in CS2's property list without a description.

## Labels and text

### Write or blank every dialog variable a layout shows

- **Symptom:** a label shows its token, `{s:balance}`, instead of text.
- **Cause:** a `{s:name}` reference has no empty default. It shows literally until the server writes `name` for that
  panel.
- **Fix:** right after spawning the entity, write every variable the layout shows, an empty string when there is
  nothing to show, or ship the label collapsed until it has text. When you add a label to a layout that other plugins
  already drive, ship it collapsed and with an `id`, so their HUDs do not start showing a token.
- **Evidence:** observed in game, 2026-09.

### Write a variable through the id of the label that shows it

- **Symptom:** a write returns, nothing changes on screen, and nothing is logged.
- **Cause:** the write names a panel id that no element in the layout carries, such as a label without an `id` or a
  stale list of ids, and the client ignores it. SwiftlyS2 v1.5.2 hands the strings to the game's own setter without
  checking them against the layout ([source][src-setters], [signatures][src-gamefunctions]).
- **Fix:** put the `id` on the Label that shows `{s:name}`, and write to that id and name. Take both from the layout
  file, and check the pairs with a script whenever the layout or the plugin changes. Whether a variable written on a
  parent panel reaches a Label below it is not established.
- **Evidence:** observed in game, 2026-09.

### Send plain text into dialog variables

- **Symptom:** `<font color='red'>` shows as literal characters. Or, after `html="true"` was added to every Label, the
  whole HUD stopped drawing with nothing in the server log.
- **Cause:** a dialog variable's value is inserted as text, not as markup. Colour tags belong to chat, and HTML to
  CenterHTML. Rendering HTML in a Label needs an `html` attribute, and a custom HUD Label may carry only `id`, `class`,
  `hittest` and `text` ([Valve][valve-allowed]), so a layout that sets it falls outside what the client accepts.
- **Fix:** colour with classes on the Label. For several colours in one line, put several Labels in a
  `flow-children: right` row, each with its own class and variable. Keep the translations that feed HUD text plain;
  when a string is shared with chat or CenterHTML output, add that markup at the call site.
- **Evidence:** the literal markup observed in game, 2026-08 and 2026-09; the blank HUD observed in game, 2026-08. That
  the client rejected the layout is inferred, not observed: its console was not read.

### Collapse an optional label instead of blanking it

- **Symptom:** a card shows a dead gap under its last visible line.
- **Cause:** a Label takes its height from the font's line box, not from its text: an empty one still takes a line of
  about 14 px, plus its margins.
- **Fix:** collapse the label with a class, since [`visibility: collapse`][pv-visibility] removes a panel from layout,
  and remove the class when the label has text. Write both the text and the class every time: one entity shows
  different messages over its life.
- **Evidence:** observed in game, 2026-10.

### Set the font on every label

- **Symptom:** labels draw in a face, size or colour that matches neither the mock nor the game's HUD.
- **Cause:** custom HUD layouts sit under a window root of their own that includes only Valve's `base.vcss`
  ([layout][valve-customhuds]), and that sheet styles nothing but the root's size ([sheet][valve-base]). The game's
  text styles do not apply. What a Label draws with no font set is not established.
- **Fix:** set `font-family`, `font-size` and `color` on every Label, or on a class every Label carries. Valve's sheets
  most often write `font-family: Stratum2, 'Arial Unicode MS';`.
- **Evidence:** Valve's files at build 2000943; the face a Label falls back to is inferred, not observed.

[sws2-authoring]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-panorama-authoring/references/authoring.md
[pv-list]: https://swiftlys2.net/panorama-viewer/cs2
[pv-width]: https://swiftlys2.net/panorama-viewer/cs2/width
[pv-flow]: https://swiftlys2.net/panorama-viewer/cs2/flow-children
[pv-position]: https://swiftlys2.net/panorama-viewer/cs2/position
[pv-overflow]: https://swiftlys2.net/panorama-viewer/cs2/overflow
[pv-visibility]: https://swiftlys2.net/panorama-viewer/cs2/visibility
[pv-ui-scale]: https://swiftlys2.net/panorama-viewer/cs2/ui-scale
[pv-text-shadow]: https://swiftlys2.net/panorama-viewer/cs2/text-shadow
[pv-box-shadow]: https://swiftlys2.net/panorama-viewer/cs2/box-shadow
[pv-texture-size]: https://swiftlys2.net/panorama-viewer/cs2/background-texture-size
[pv-z-index]: https://swiftlys2.net/panorama-viewer/cs2/z-index
[valve-styles]: https://github.com/SteamDatabase/GameTracking-CS2/tree/82e2b9d62cc97f1358c68a220a4a392c9e41c509/game/csgo/pak01_dir/panorama/styles
[valve-customhuds]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/game/csgo/pak01_dir/panorama/layout/hud/customhuds.xml
[valve-base]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/game/csgo/pak01_dir/panorama/styles/base.css
[valve-hudrush]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/game/csgo/pak01_dir/panorama/styles/hud/hudrush.css#L27
[valve-allowed]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/content/csgo_addons/cs_script_demo/maps/scripts/point_script.d.ts#L1041-L1045
[valve-hud-classes]: https://github.com/SteamDatabase/GameTracking-CS2/blob/82e2b9d62cc97f1358c68a220a4a392c9e41c509/content/csgo_addons/cs_script_demo/maps/scripts/point_script.d.ts#L1047-L1054
[src-setters]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Schemas/Extensions/CCSCustomHudLayoutImpl.cs#L53-L63
[src-gamefunctions]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Natives/GameFunctions.cs#L116-L121
