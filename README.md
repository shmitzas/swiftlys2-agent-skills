# swiftlys2-agent-skills

Markdown docs for building [SwiftlyS2](https://swiftlys2.net) plugins for Counter-Strike 2, porting plugins from CounterStrikeSharp, building custom Panorama HUDs, and creating CS2 assets with Blender and Source2Viewer-CLI, written for coding agents and the people who use them. Each skill is a folder that starts at its `SKILL.md`, in the [Agent Skills](https://agentskills.io/specification) format; `sw2-asset-pipeline` also ships the Blender and inspection scripts it runs. Read the skills here, or clone the repository and point your agent at it.

## Skills

| Skill | Use it for | Pages |
| --- | --- | --- |
| [sw2-plugin-pitfalls](skills/sw2-plugin-pitfalls/SKILL.md) | Bugs that build cleanly and then misbehave: lifecycle and reload, commands, events, entities, players, threads, shared interfaces, persistence, packaging, and CounterStrikeSharp habits | [lifecycle and reload](skills/sw2-plugin-pitfalls/references/lifecycle-and-reload.md), [commands and text](skills/sw2-plugin-pitfalls/references/commands-and-text.md), [events and hooks](skills/sw2-plugin-pitfalls/references/events-and-hooks.md), [entities and weapons](skills/sw2-plugin-pitfalls/references/entities-and-weapons.md), [players and identity](skills/sw2-plugin-pitfalls/references/players-and-identity.md), [threads and scheduler](skills/sw2-plugin-pitfalls/references/threads-and-scheduler.md), [dependencies and contracts](skills/sw2-plugin-pitfalls/references/dependencies-and-contracts.md), [persistence](skills/sw2-plugin-pitfalls/references/persistence.md), [packaging and release](skills/sw2-plugin-pitfalls/references/packaging-and-release.md), [CounterStrikeSharp habits](skills/sw2-plugin-pitfalls/references/counterstrikesharp-habits.md) |
| [sw2-plugin-audit](skills/sw2-plugin-audit/SKILL.md) | Review a plugin or a change against enumerated checklists, with a severity rubric | [procedure](skills/sw2-plugin-audit/references/procedure.md), [checklists](skills/sw2-plugin-audit/references/checklists.md), [contracts](skills/sw2-plugin-audit/references/contracts.md), [severity and report](skills/sw2-plugin-audit/references/severity-and-report.md) |
| [sw2-asset-pipeline](skills/sw2-asset-pipeline/SKILL.md) | Build models in Blender, deliver and precache them from a plugin; routes legacy-asset porting to cs2-skills | [procedural models](skills/sw2-asset-pipeline/references/procedural-models.md), [weapon frames](skills/sw2-asset-pipeline/references/weapon-frames.md), [props and pickups](skills/sw2-asset-pipeline/references/props-and-pickups.md), [compile and inspect](skills/sw2-asset-pipeline/references/compile-and-inspect.md), [delivery from SwiftlyS2](skills/sw2-asset-pipeline/references/delivery-from-swiftlys2.md), [ModSharp to SwiftlyS2](skills/sw2-asset-pipeline/references/modsharp-to-swiftlys2.md) |
| [cs2-panorama-hud](skills/cs2-panorama-hud/SKILL.md) | Panorama CSS and text traps, per-player HUD state, input routes, mock-first design and delivery checks for custom HUDs | [Panorama CSS and text](skills/cs2-panorama-hud/references/panorama-css-and-text.md), [per-player HUD state](skills/cs2-panorama-hud/references/per-player-hud-state.md), [input](skills/cs2-panorama-hud/references/input.md), [mock-first workflow](skills/cs2-panorama-hud/references/mock-first-workflow.md), [delivery checks](skills/cs2-panorama-hud/references/delivery-checks.md) |

Start at a skill's `SKILL.md`: it says when the skill applies and which page answers which question.

## Use

Read the skills on GitHub, starting from the table above, or clone the repository:

```sh
git clone https://github.com/shmitzas/swiftlys2-agent-skills
```

Give an agent the skills in either of two ways:

- **Point it at this README.** Add a line like this to your agent's instructions file, such as `AGENTS.md`, `CLAUDE.md` or `.github/copilot-instructions.md`:

  ```text
  For SwiftlyS2 plugins, Panorama HUDs and CS2 assets, read <clone>/README.md and open the matching skill.
  ```

  An agent that fetches URLs can read `https://raw.githubusercontent.com/shmitzas/swiftlys2-agent-skills/main/README.md` instead of a clone: the relative links in every page resolve to raw pages too.
- **Copy the skills into a skills directory.** Copy or symlink every folder inside `skills/` into a directory your agent loads skills from. The agent then opens a skill when the task matches its `description`.

  | Agent | Project | Personal |
  | --- | --- | --- |
  | GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
  | Claude Code | `.claude/skills/` | `~/.claude/skills/` |
  | OpenAI Codex | `.agents/skills/` | `~/.agents/skills/` |

Keep the skill folders together, because they link to each other. Run `git pull` in the clone to update; symlinked folders update with it.

For API lookups, add the SwiftlyS2 MCP server, `https://swiftlys2.net/api/mcp` (Streamable HTTP), to an agent that supports MCP. It is optional: without it, the skills use the fallbacks [below](#how-the-skills-are-written).

## How the skills are written

- Every framework claim links its evidence: a page on swiftlys2.net or a SwiftlyS2 source file at a tagged release. Engine claims can also link Valve's files at a pinned [GameTracking-CS2](https://github.com/SteamDatabase/GameTracking-CS2) commit. Each skill states the SwiftlyS2 version it was checked against and how each behaviour was established: seen in production or in game, reproduced in a test, or only read from source.
- API declarations are not copied. The skills look them up through the SwiftlyS2 MCP, which serves the current `stable` and `beta` branches, and check the result against the SwiftlyS2 package version the plugin builds with. When an agent has no SwiftlyS2 MCP or cannot reach it, the skills send it to swiftlys2.net and a fresh download of [`llms-full.txt`](https://swiftlys2.net/llms-full.txt), which has every docs page but no API reference; declarations then come from the SwiftlyS2 source at the package version's tag.
- They add to, rather than repeat, [SwiftlyS2-Skills](https://github.com/btnrv/SwiftlyS2-Skills) and the engine-neutral steps in [cs2-skills](https://github.com/AbsilDylan/cs2-skills).

## Contributing

Run `python tools/validate_skills.py` before opening a pull request. It checks skill names and descriptions against the Agent Skills specification, checks inline relative links, and fails on local paths or agent memory notes.

## License

[AGPL-3.0-only](LICENSE).
