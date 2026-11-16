# Severity and the report

How to grade a finding, what a finding contains, and the report that ends each audit round.

## Severity

Grade a finding by what it does on a server that runs the plugin, not by how the code looks. When one cause has
several effects, grade it by the worst and report it once. A Blocker or a Major makes the round FAIL; Minor findings,
Observations and Questions do not.

### Blocker

The change must not ship: a crash, a plugin or host that fails to load, data loss, a security hole, game state used
off the game thread, a build failure, an unapproved contract change, or a regression, meaning behaviour that worked at
the base and fails at the head. For example:

- A method that always runs names a soft dependency's contract type: on servers without the provider, `Hosting failed
  to start` and no plugin loads ([rule][si-soft]).
- A handshake method lets an exception escape, which ends the handshake for every plugin after it ([rule][si-throw]).
- Code after an `await` reads `player.PlayerPawn` ([rule][ts-copy]).
- A failed load caches an empty record, and a get-or-default helper saves defaults over the stored values
  ([rule][pe-failed]).
- A translation file no longer parses, so the plugin does not load ([rule][ct-translation-files]).
- A setting renamed without its stored key name: every server quietly runs on the default ([rule][lr-key-name]).
- A client-command hook returns `Stop` before it checks which command it got: players can no longer chat
  ([rule][ct-filter]).
- The plugin calls a member that the SwiftlyS2 version it declares lacks: `MissingMethodException` on those servers
  ([rule][pk-version]).

### Major

A defect to fix before the round can pass: a bug in behaviour the change adds, a broken rule of the repo's guide, a
missing release, a key missing from `en.jsonc`, an unrequested change, or a document the repo requires left stale. For
example:

- A new disconnect handler tests `IsValid`, so it skips players without a pawn and their state stays
  ([rule][pi-controller]).
- A new reward timer uses `RepeatBySeconds`, so it pays every connected player whenever the plugin loads
  ([rule][ts-timer]).
- A new hook meant to block an action returns `Handled`, and the action still happens ([rule][eh-result]).
- A handler the change registers in `UseSharedInterface` runs once more after every plugin load and unload
  ([rule][si-bind]).
- A per-player collection the change adds gains an entry on join and never loses it ([rule][pe-evict]).
- Settings the change copies in `Load` ignore config edits until a reload ([rule][lr-monitor]).
- A key the new code uses is missing from `en.jsonc`, so players read `<language>.<key>`
  ([rule][ct-missing]).
- An internal refactor or rename nobody asked for.
- A new command left out of the README's command table, where the repo keeps one.

### Minor

Worth fixing, and no reason to hold the change: a deviation from the surrounding code's style, comment noise, a small
documentation gap, or a check or release the framework already provides. For example:

- `IsValid` tested on players that `GetAlive()` returned ([guarantees][sws2-guarantees]).
- `SteamID` read three times in a loop body that runs every tick ([read a property once][sws2-read-once]).
- A comment that repeats the statement below it.
- A key in `en.jsonc` that another shipped language lacks, so that language's players read English. It is Major where
  the repo requires complete language files ([rule][ct-missing]).
- `Unload` unregistering commands that unloading unregisters anyway, in code no other path runs ([rule][lr-unload]).

### Observation

A problem that was already there at the base. It never changes the verdict; report it so the owner can schedule it. A
problem the change causes in code it did not touch is not an Observation: it is a finding at that location, graded
like any other.

### Question

Something the docs, the source and the diff cannot settle. It is not a finding; the owner answers it.

## What a finding contains

- **ID and severity**, such as `F3 [Major]`. A finding keeps its ID in later rounds.
- **Location:** `path:line` in the audited head, and every location when one cause shows in several places.
- **Problem:** what is wrong, in one sentence.
- **Evidence:** a rule quoted in one line, with the page and section it comes from, such as a `sw2-plugin-pitfalls`
  rule, a checklist item or a heading of the repo's guide; or a concrete failure: the input, then the wrong outcome.
  Without either, it is not a finding. When the rule is inferred from source and not observed, say so.
- **Why it matters:** what a player, an operator or another plugin sees, and when.
- **Fix:** the smallest change that removes the cause, in the plugin's style.

```text
F3 [Major] src/Features/Interest.cs:42
  Problem: RepeatBySeconds(3600, PayInterest) pays interest when the plugin loads, then hourly.
  Evidence: sw2-plugin-pitfalls, threads-and-scheduler, "Use DelayAndRepeat* unless the first run may happen now".
  Why it matters: each restart, reload and update pays every connected player once more.
  Fix: DelayAndRepeatBySeconds(3600, 3600, PayInterest).
```

## The report

```text
VERDICT: PASS | FAIL
Round: <n> of 3
Scope: <repo>; base <sha>; head <sha, or "working tree">; <files audited>
Excluded: <changes that were already there, or "none">
Request: <one line>
Contracts: <unchanged | added: <list> | changed: <list>, approved or not>
Findings:
  <ID> [Blocker | Major | Minor] <path:line>: <problem>. Evidence: <rule | failure>. Fix: <smallest fix>.
Previous findings: <ID: fixed | still open | no longer applies, because <reason>>
Checklists: <sections walked; items failed, not applicable or unchecked, each with its reason>
Gates: <build and warnings in changed files; tests; format or analyzers; archive listing; translation key counts>
Lists: <the inventory, and what each search matched>
Not checked: <what this round could not verify, and why>
Observations: <already there at the base, or "none">
Questions: <for the owner, or "none">
```

- **VERDICT** is PASS when the round found no Blocker and no Major, and FAIL otherwise.
- **Previous findings** starts in the second round, and lists every earlier finding.
- **Not checked** names in-game behaviour, servers and plugins the reviewer could not see, and gates that could not
  run. A PASS covers only what was checked.

[ct-translation-files]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#ship-enjsonc-and-keep-each-translation-file-parseable
[ct-missing]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#detect-a-missing-translation-by-its-language-prefix
[lr-unload]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#release-only-what-unloading-leaves-behind-and-let-unload-return
[sws2-guarantees]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md
[sws2-read-once]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/guarantees.md#read-a-property-once
[si-soft]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#keep-a-soft-dependencys-contract-types-out-of-methods-that-always-run
[si-throw]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#let-nothing-escape-a-handshake-method
[si-bind]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#bind-fail-closed-and-register-nothing-in-the-handshake
[ts-copy]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#copy-values-before-leaving-the-game-thread
[ts-timer]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#use-delayandrepeat-unless-the-first-run-may-happen-now
[pe-failed]: ../../sw2-plugin-pitfalls/references/persistence.md#treat-a-failed-load-as-unknown-not-as-empty
[pe-evict]: ../../sw2-plugin-pitfalls/references/persistence.md#evict-per-player-caches-on-disconnect-and-sweep-ttl-caches
[lr-key-name]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#keep-the-stored-key-name-when-renaming-a-setting
[lr-monitor]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#read-settings-through-the-monitor-not-a-copy
[ct-filter]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#filter-a-client-command-hook-to-its-own-command-first
[pk-version]: ../../sw2-plugin-pitfalls/references/packaging-and-release.md#build-against-the-oldest-swiftlys2-you-support-and-declare-it
[pi-controller]: ../../sw2-plugin-pitfalls/references/players-and-identity.md#gate-join-chat-menu-and-disconnect-paths-on-the-controller
[eh-result]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#return-stop-or-canceloriginal-to-block-an-action
