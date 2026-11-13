# Working on @dialecte/create

Every coding agent working in this repository reads this file. Notes that hold only for one machine (local
paths, where the standard's text lives, a person's working setup) go in `AGENTS.local.md` beside it, which git
ignores; read it when it exists.

## First commands

<!-- dialecte-skills:session-check -->

At the start of a session, run `npx --no-install @dialecte/cli doctor --brief`: nothing printed means the Dialecte skills are in sync; otherwise each line is a problem with its fix.

<!-- /dialecte-skills:session-check -->

When it says so, run `npx dialecte skills sync`.

## Skills to load

Load `dialecte-create` (this repository's own skill, under `skills/`) first; to run a lot, `dialecte-lot`, which
ships with `@dialecte/core` (`npx dialecte skills sync --from <workspace>` installs it from a local checkout).

## Before writing code

The generator derives a dialecte from its schema: read the derivation and its tests before adding a case, and
derive from the schema rather than hand-writing what it says. `npx dialecte api find "<need>" --source` searches
this repository's own code.

## Answers

Lead with the result; keep a reply short: no repetition, no filler, in whole sentences a person can read in one
pass.

## Code rules

1. Never `any`.
2. Always narrow types.
3. Types in `*.types.ts`, constants in `*.constants.ts`; named functions; object parameters; no `await` inside
   an argument (`npx dialecte rules <files>` checks these).
4. Immutable operations: never mutate an input; return new values.
5. Files grouped by concern, not by technical layer.
6. Explicit context: no hidden state.
7. The Python generator under `python/` follows the same intent: type hints on every function, pure functions,
   files grouped by concern.
8. The template under `templates/dialecte/` is a dialecte package: it follows the rules its own `AGENTS.md`
   states.

## Definition of Done

Tests first, red before green.

- Every step: the touched cases red, then green, with `npm run test:ts` (TypeScript) or `npm run test:py` (the
  generator), then `npm run check` and `npx dialecte rules` on the touched files.
- Every behaviour: `npx dialecte gate --fast`.
- Every lot: `npx dialecte gate --full` once, before the hand-over (its steps are in `package.json`,
  `dialecte.gate`), and `npm run proof`; a change under `templates/` also runs `npm run test:cli`.
- A visible change adds a `## [Unreleased]` entry to `CHANGELOG.md` and updates the skill under `skills/`
  (`npm run skills:generate`, then `npm run skills:check`), in the same change.

## Stations

In a lot, each station changes only what its role may change (the role rule in `dialecte-lot`): reviewers change
nothing; the test station changes tests, test data and stub production code; the implementer changes production
code in scope and the CHANGELOG; only the lot session deletes.

## Never

- Commit, stage, push, stash, `git reset` / `restore` / `checkout --`, switch branches, or edit under `.git`,
  unless the person asks.
- Write a real person's name or handle in a committed file, test values included (use `reviewer`, `person-a`).
- Name a tool that consumes the package, a coding-agent host or a model in a committed file.
- Put the standard's text, file names or clause numbers in a committed file.
- Edit a generated file by hand (regenerate it).
