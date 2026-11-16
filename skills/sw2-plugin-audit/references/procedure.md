# Run an audit round

How to audit a SwiftlyS2 plugin, or a change to one, in one round, and how to run the next round after fixes. The
questions are in [checklists.md](checklists.md), the contract rules in [contracts.md](contracts.md), and the severity
scale and report template in [severity-and-report.md](severity-and-report.md).

Start from the request the change answers, word for word, the plan if there is one, and the list of approved contract
changes. From the second round on, also take the previous report and the author's account of the fixes.

## 1. Fix the scope

1. Find the base, the commit the change started from. Record it with `git rev-parse HEAD` before the change begins.
   For a branch or a pull request, the base is `git merge-base <target-branch> <head>`.
2. Record the changes that were already there: `git status --short` at that moment. They can be another person's
   work in progress. Leave them out of the diff, never revert them, and report what you notice in them as
   Observations. When tracked files already had changes, `git stash create` prints a commit that records them without
   touching the working tree or the stash list; use that commit as the base.
3. Take the diff: `git diff <base>` for a working tree, or `git diff <base> <head>` for commits, plus each untracked
   file from `git ls-files --others --exclude-standard` that was not on the recorded list. With no recorded base,
   audit `git diff HEAD` plus the untracked files, and say so in the report.
4. List the changed files and the symbols in them. A whole-plugin audit has no diff: name the commit, and the scope is
   the plugin.
5. Read the request, then the diff. When bug reports come with the request, [build the
   inventory](#3-build-the-inventory) before you read them: named symptoms pull attention from the rest of the change.

## 2. Read the plugin's own conventions

1. Read the repo's guide, where it has one, by the headings the diff touches: a contributor guide, agent instruction
   files such as `AGENTS.md` or those under `.github/`, the README and the changelog.
2. Without a guide, the surrounding code is the convention. Before judging a changed file, read two of its neighbours
   for naming, layout, logging, translations, config shape, error handling and changelog style.
3. Hold the plugin to its own conventions. A logging policy, permission scheme or layout from another project is not
   a finding.
4. A guide adds rules and cannot switch off how SwiftlyS2 behaves. Where a guide line contradicts the framework, the
   framework decides the finding, and the line goes in the report as an Observation.

## 3. Build the inventory

List what the change adds, changes or touches; for a whole-plugin audit, list everything. Each list feeds the
checklist sections in its row.

| List | With | Walk |
| --- | --- | --- |
| Commands | Each command and alias, from attributes, code and config, with its permission | C |
| Handlers and subscriptions | Each core-event, game-event, game-hook, client-command and client-chat handler, and each config change subscription, with where it is registered and what releases it | C, E, L, P, T, X16, X17 |
| Menus | Each menu, classic or `Core.Menu`, with what its clicks do | P, T, [other skills' checks](checklists.md#other-skills-checks) |
| Timers and background work | Each scheduler call, `Task.Run`, and database or HTTP continuation, with what stops it | T, X16, X17 |
| Shared interfaces | Each key published or consumed, and each provider event subscribed | S, X16 |
| Settings | Each key with its default, its clamp and where it is read | L |
| Player state | Each collection keyed by a player, with the line that removes the entry | P, D |
| Persistence | Each table, migration and persisted key | D |
| Translations | The keys the code uses, and the keys in each language file | X, C |
| Contracts | Everything above that something outside the diff depends on | [contracts.md](contracts.md) |

Show the lists in the report. A list makes an item checkable: "every handler is released" passes on a glance at
`Unload`, while a table that pairs each registration with the line or framework step that releases it shows the gap.

## 4. Identify the contracts touched

Mark each contract on the inventory as unchanged, added or changed, using [contracts.md](contracts.md). List every
addition in the report. A changed contract that is not on the approved list is a Blocker.

## 5. Walk the checklists

1. Walk [every change](checklists.md#every-change-x), then the section of each subsystem the change touches, from
   [the table in checklists.md](checklists.md).
2. Follow the blast radius: the callers of each changed method, the consumers of each changed interface or event, the
   release of everything registered, and any other path that performs the same operation.
3. Answer each item: pass, fail, not applicable with the reason, or unchecked with the reason. Each fail becomes a
   finding.
4. Take timing, threads and re-entrancy from the docs or the source, never from the shape of a call:
   `RepeatBySeconds(3600, Pay)` reads as hourly and [runs now, then hourly][ts-timer].
5. Search beyond the plugin for the names every plugin on a server shares: commands and aliases, permission strings,
   shared-interface keys, plugin IDs, database tables ([command names][ct-names]), convar names and `Core.Menu` menu
   IDs ([contracts](contracts.md)). Creating a convar whose name exists throws ([`ConVarService.cs`
   L84-L87][src-convar-create]; inferred from source, not observed). Search the other plugins you have, and list what
   you could not search under "Not checked".
6. Report what each search matched. A search that finds no problems proves nothing until it is shown to find what it
   looks for, so give the number of matches next to the number of problems.

## 6. Run the gates

Run what the repo's CI runs, from the plugin root or with the solution the repo builds. Without CI, start with a
Release build that compiles everything again:

```text
dotnet build -c Release --no-incremental
```

1. Rebuild from scratch so that warnings are reported again. An up-to-date build skips compilation and repeats none,
   and `dotnet clean` without `-c Release` cleans only the Debug build ([clean output][pk-clean]). List the warnings in
   changed files. An obsolete warning on a game-event member is a bug, not noise ([`player_hurt`][eh-hurt]).
2. Run the tests with `dotnet test` where the repo has them, and its format or analyzer check, such as
   `dotnet format --verify-no-changes`, where it uses one.
3. Dry-run the package from clean outputs. Clean the `bin`, `obj` and `build` folders of the plugin project and, for
   a provider, of the contract project, and `resources/exports`, as the [exports rule][si-target] does. List what git
   ignores in them with `git clean -ndX -- <folders>`, then remove it with `git clean -fdX -- <folders>`, which leaves
   tracked files alone. `git status --short -- <folders>` marks with `??` the untracked files git does not ignore:
   they stay, and go in the report, since a clean checkout would not have them. Then run `dotnet publish -c Release`
   and list the archive the template writes to `build/`. Check that the plugin folder and DLL names
   [match in case][pk-case], the resources are there, no SwiftlyS2 assembly is
   ([template and distribution][sws2-layout]), a provider's archive holds its contract [exactly once][si-one-copy],
   under `resources/exports`, and a consumer's holds no copy of the contracts it consumes.
4. Publish a template project without `-o`. The template zips the folder above the publish folder, so with `-o` it
   also zips whatever sits next to the folder you named.
5. Count the translation keys in each language file, and list the keys each file lacks against the keys the code uses.
6. Leave the repo as you found it. Outputs git ignores are fine; anything else goes in a scratch folder outside the
   repo. A gate that fails only because the author's running build holds a file is a retry, not a finding.

**Evidence** for the clean in step 3: git's [`git clean`][git-clean]. Reproduced in a test, with tracked, ignored and
untracked files in those folders. For step 4: the template's [`PluginId.csproj` L11-L12][src-template-paths] and
[L34-L40][src-template-zip]; Microsoft's [`dotnet publish`][ms-publish]. Reproduced in a test, with a project that
copies the template's output paths and zip target.

A build shows that the types line up, not what the game does. Put what needs a running server under "Not checked".

## 7. Prove and grade each finding

1. Locate the finding at `path:line` in the audited head, and read the code there again before you write it down. For
   something missing, such as a release or a translation key, point at the line that needs it.
2. Back it with a rule or a concrete failure, as [a finding](severity-and-report.md#what-a-finding-contains) requires.
3. Check the rule against the SwiftlyS2 version the plugin builds with: the `SwiftlyS2.CS2` version in its project
   file or, when that floats, the version restored in `obj/project.assets.json`, which `dotnet list package` prints as
   Resolved. Not the newest release.
4. Carry the rule's evidence level: a finding that rests on a rule inferred from source says so.
5. Grade it on the [severity scale](severity-and-report.md#severity). A problem already there at the base is an
   Observation; a problem the change causes in code it did not touch is a finding at that location.
6. Propose the smallest fix, in the plugin's style. Ask for nothing the plugin's rules do not: no features, tests,
   abstractions or style changes of your own.
7. When the docs, the source and the diff cannot settle how something behaves, ask it as a Question.

## 8. Write the report

Fill in the [report template](severity-and-report.md#the-report). List what you did not check as carefully as what you
did: a PASS covers only what was checked.

## Re-audit

The next round goes to a reviewer who did not write the fixes, as [the audit loop](../SKILL.md#the-audit-loop)
describes.

1. Keep the base of the first round. Take the new head, the previous report and the author's account of the fixes.
2. Verify each previous finding at the new head: fixed, still open, or no longer applicable with the reason. Re-run
   the search or gate that found it.
3. Audit the whole diff from the base to the new head again, from step 1, not only the fixes. A fix moves code that
   earlier rounds passed, and can wake code that never ran: a fix that turned on reload-on-change made a config seeder
   that wrote its file run on every reload, and the plugin [reloaded several times a second][lr-write-back].
4. Keep the finding IDs of earlier rounds, and number new findings after them.
5. Stop at PASS. After a third round without one, the loop escalates to the owner.

[ms-publish]: https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-publish
[git-clean]: https://git-scm.com/docs/git-clean
[sws2-layout]: https://github.com/btnrv/SwiftlyS2-Skills/blob/main/skills/sws2-authoring/references/architecture/layout.md#template-and-distribution
[ts-timer]: ../../sw2-plugin-pitfalls/references/threads-and-scheduler.md#use-delayandrepeat-unless-the-first-run-may-happen-now
[ct-names]: ../../sw2-plugin-pitfalls/references/commands-and-text.md#give-each-command-and-alias-a-name-no-other-plugin-uses
[pk-clean]: ../../sw2-plugin-pitfalls/references/packaging-and-release.md#publish-a-release-from-a-clean-output-folder
[pk-case]: ../../sw2-plugin-pitfalls/references/packaging-and-release.md#match-the-case-of-the-plugin-folder-dll-and-project-names
[eh-hurt]: ../../sw2-plugin-pitfalls/references/events-and-hooks.md#read-player_hurt-values-from-the-actual-members
[si-one-copy]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#ship-exactly-one-copy-of-the-contract-in-resourcesexports
[si-target]: ../../sw2-plugin-pitfalls/references/dependencies-and-contracts.md#collect-generated-exports-inside-a-target
[lr-write-back]: ../../sw2-plugin-pitfalls/references/lifecycle-and-reload.md#never-write-the-watched-file-from-a-change-callback
[src-template-paths]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/SwiftlyS2.PluginTemplate/templates/PluginId.csproj#L11-L12
[src-template-zip]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/SwiftlyS2.PluginTemplate/templates/PluginId.csproj#L34-L40
[src-convar-create]: https://github.com/swiftly-solution/swiftlys2/blob/v1.5.2/managed/src/SwiftlyS2.Core/Modules/Convars/ConVarService.cs#L84-L87
