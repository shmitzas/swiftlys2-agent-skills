---
name: sw2-plugin-audit
description: >-
  Audit a SwiftlyS2 plugin for Counter-Strike 2, or a change to one, in rounds by a reviewer who did not write it: fix
  the scope from the diff, read the plugin's own conventions, find the contracts it touches, walk numbered checklists
  for each subsystem it touches, run the repo's build, test and packaging gates, prove each finding at file:line,
  grade it Blocker, Major or Minor, and report a PASS or FAIL verdict. Checklist items link to the sw2-plugin-pitfalls
  rules and SwiftlyS2-Skills' framework guarantees instead of restating them. Use when asked to audit or re-audit a
  plugin, review a plugin, a pull request or a diff, check a change before a release, or verify a fix; and when
  deciding whether a change to config keys, database schema, commands, permissions, translation keys or a shared
  interface needs the owner's approval.
---

# Audit a SwiftlyS2 plugin

A procedure for reviewing a SwiftlyS2 plugin, or a change to one, so that two reviewers who read the same diff reach
the same verdict.

SwiftlyS2-Skills' [framework guarantees][sws2-guarantees] page answers one review question: which checks the framework
already made, so that the code can drop them. Its authoring skill asks for a [review of custom code][sws2-review]
before delivery. This skill builds the rest of the review around them: the scope, the contracts, the checklists, the
gates, a severity scale, the report and the loop of rounds. Its checklist items are questions; the rules that answer
them, with their evidence, live in [`sw2-plugin-pitfalls`](../sw2-plugin-pitfalls/SKILL.md) and SwiftlyS2-Skills, and
the items link them rather than restating them.

Checked against SwiftlyS2 v1.5.2 (2026-11-12) and SwiftlyS2-Skills at commit `b8ce269`. An item carries the evidence
level of the rule it links. The framework claims this skill makes itself, about plugin identity, convars, menu
configuration and the template's archive, cite the SwiftlyS2 source at the v1.5.2 tag, and each says how it was
established.

Look up the behaviour a finding rests on through the SwiftlyS2 MCP or [swiftlys2.net][docs], at the SwiftlyS2 version
the plugin builds with. If the MCP is unreachable, download a fresh copy of [`llms-full.txt`][docs-llms-full] and
search it rather than reading it whole; each docs page in it starts at a line beginning
`## https://swiftlys2.net/docs`. It has no API reference, so take exact declarations from the SwiftlyS2 source at the
tag of the package version the plugin builds with.

## Pages

| Page | Use it for |
| --- | --- |
| [procedure.md](references/procedure.md) | One audit round, from fixing the scope to the report, and the re-audit |
| [checklists.md](references/checklists.md) | Numbered questions for every change and for each subsystem, linked to the rules that answer them |
| [contracts.md](references/contracts.md) | What counts as a contract in a SwiftlyS2 plugin, what may change without approval, and what an approval request contains |
| [severity-and-report.md](references/severity-and-report.md) | Blocker, Major and Minor with examples, what a finding contains, and the report template |

## The audit loop

A round is one review of the change by a reviewer who did not write it: ideally a fresh session or agent, or another
person, so that the author's reasoning does not carry over. Give every round's reviewer the same packet: the request
word for word, the plan, the approved contract changes, the base and the changes that were already there, and the
author's report; from the second round, also the previous report.

1. **Audit.** The reviewer runs [one round](references/procedure.md) and returns a report with a verdict.
2. **Fix.** On FAIL, the author fixes every Blocker and Major. A Minor finding is fixed when the fix is trivial and
   inside the request; otherwise it stays in the report.
3. **Re-audit.** A reviewer who did not write the fixes verifies each previous finding, then audits the whole diff from
   the original base again ([re-audit](references/procedure.md#re-audit)).
4. **Stop** at PASS: no Blocker and no Major. After three rounds without a PASS, stop and give the owner the open
   findings and what each round changed.

A person reviewing by hand follows the same loop. The author never signs off their own change.

## Rules

1. Review without editing. A reviewer who changes the code under audit becomes its author.
2. The scope is the diff from the base and what it affects. Changes that were already there are not the author's.
3. An item without an answer is unchecked, not passed. Show the lists behind each answer.
4. Every finding has a location, and a cited rule or a concrete failure ([what a finding
   contains](references/severity-and-report.md#what-a-finding-contains)).
5. Grade by what the problem does on a server that runs the plugin.
6. Ask for nothing the plugin's rules do not require: no features, tests, abstractions or style changes of your own.
7. Problems already there at the base are Observations and never change the verdict. A problem the change causes in
   code it did not touch is a finding at that location.
8. Settle framework behaviour from the docs or the source at the plugin's SwiftlyS2 version. What they cannot settle
   is a Question, not a finding.

## What a reviewer can do alone

From the repository alone, a reviewer can read the diff and its blast radius, search the plugin and the other plugins
at hand, build, test, publish and list the archive. That shows what the code does, not what the game does. For each
finding or item that depends on the game, hand the owner a check to run on a server, such as:

- reload the plugin twice, then count how often one event runs its handler;
- join after the plugin has loaded, and disconnect while the feature is active;
- start a server without each soft dependency;
- change the map, and restart the round, while the feature runs.

## What lives elsewhere

| Topic | Go to |
| --- | --- |
| The rules the checklists ask about, with symptoms and evidence | This pack's [`sw2-plugin-pitfalls`](../sw2-plugin-pitfalls/SKILL.md) |
| Checks the framework already made; custom code that repeats the framework | SwiftlyS2-Skills [framework guarantees][sws2-guarantees] and [framework reuse][sws2-review] |
| Plugin structure, commands, events, configuration | SwiftlyS2-Skills [`sws2-authoring`][sws2-authoring] |
| HUD layouts and per-player HUD state | This pack's [`cs2-panorama-hud`](../cs2-panorama-hud/SKILL.md) |
| Models, precache and Workshop packing | This pack's [`sw2-asset-pipeline`](../sw2-asset-pipeline/SKILL.md) |
| Menus | SwiftlyS2-Skills [`sws2-menus`][sws2-menus] |

[docs]: https://swiftlys2.net
[docs-llms-full]: https://swiftlys2.net/llms-full.txt
[sws2-authoring]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/SKILL.md
[sws2-guarantees]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md
[sws2-review]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/framework-reuse.md#review-custom-code
[sws2-menus]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-menus/SKILL.md
