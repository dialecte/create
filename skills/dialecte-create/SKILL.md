---
name: dialecte-create
description: Create a new dialecte package from an XSD schema with @dialecte/create (npm create @dialecte), regenerate the definition of an existing dialecte (scl, nsd, plc or your own) after a schema change, and run the generator's own gates (proof, corpora, mutation tests) when changing create itself. Also covers the dialecte CLI for type coverage and type benchmarks. Use it when the user has an XSD and wants a typed TypeScript API over its XML, asks to scaffold or regenerate a dialecte, edits a *.generated.ts by mistake, or works in the create or cli repo. Load dialecte (usage) alongside, and dialecte-contributing for repo rules.
license: MIT
metadata:
  author: dialecte
  version: '0.1.0'
---

<!-- dialecte-skills workspace -->

# Creating and regenerating a dialecte

`@dialecte/create` reads an XSD (any XSD, not only SCL: the goal is to follow the XML Schema
standard as a whole, with libxml2 as the reference) and writes three generated files - the
definition, derived constants and types - plus, when scaffolding, a full package around them.

## Scaffold a new dialecte package

```bash
npm create @dialecte -- path/to/schema.xsd --name @acme/my-dialecte
# options: --out <dir>  --version <folder name, default v1>  --root <root element>  --core-version <range>
cd <out dir>   # default ./<dialecte id>, printed by the command
npm install && npm run format:fix
```

What you get (`src/<version>/`):

| Path                          | What                                                                       | Edit?                                                                |
| ----------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `definition/*.generated.ts`   | DEFINITION, constants, types                                               | never - regenerate                                                   |
| `config/`                     | the dialecte config, namespaces, `namespace <Name>` hydrated types         | yes                                                                  |
| `dialecte.ts`                 | `create<Name>Project({ storage, extensions, dev })`                        | yes                                                                  |
| `extensions/hello-world/`     | an example extension (a query + a transaction + table tests)               | copy its shape, then delete it and its line in `extensions/index.ts` |
| `test/`                       | `run<Name>TestCases` (generic / withoutExport / withExport), XML validator | extend                                                               |
| `docs/`, `.github/workflows/` | VitePress docs, CI (build, lint, test, type perf, publish, docs)           | yes                                                                  |

Then add hooks and extensions following the `dialecte` and `dialecte-contributing` skills; the
example's header comment explains the extension rules (first parameter = query/tx typed with
`Core.Query<Config>`, one function per file, table-driven test next to it).

## Regenerate an existing dialecte's definition

```bash
npx @dialecte/create generate --entry path/to/entry.xsd --out-dir <pkg>/src/<version>/definition [--root <Root>]
```

- Writes only the three `*.generated.ts` files, formatted with the target package's oxfmt.
- Schema sidecars (`parent-mapping.json`, `attribute-mapping.json`) sit next to the entry XSD.
- After regenerating: run the package's full Definition of Done; expect type-bench movement and
  explain it; review the generated diff (`create`'s `definition:diff` script helps).
- If a generated file looks wrong, fix the generator (or the schema input), never the output.

## Changing create itself

- Four parts: the Python XSD reader (`python/generate`, run in Node through Pyodide), the TS
  derivation (`src/derive`), the CLI (`src/cli`) and the template (`templates/dialecte`).
- Fast checks while iterating: `npm run check`, `npm run test:ts`, `npm run test:py`, targeted
  fixtures. Template changes: `npm run test:cli` / `test:cli:install`.
- Once per lot before hand-over: `npm run proof` (types, lint, format, Python + TS suites with
  libxml2 oracles, construct inventory, fixture regeneration, and - when sibling dialecte repos are
  present - re-deriving their constants and types). Corpora (`corpora:fetch`, `test:corpora`,
  never committed) and mutation tests (`mutants`, `mutants:ts`; surviving mutants recorded with a
  reason) for generator changes.
- Core's test schema (`core/src/test/generated/test.xsd`) follows a fixed dummy convention:
  branches `X → XX_n → XXX_n`, `_1` required, `_2` maxOccurs 2, `_3` in the ext namespace,
  attributes `aX` required / `bX` optional / `ext:cX`; extra letters for special cases. Never
  descriptive names. Keep core's and create's copies identical, regenerated through create.

## Type performance CLI (`@dialecte/cli`, bin `dialecte`)

Zero-config on a dialecte package (finds `src/<version>/definition/*.generated.ts`):

| Script in the package | Command                  | Purpose                                    |
| --------------------- | ------------------------ | ------------------------------------------ |
| `coverage:gen`        | `dialecte coverage`      | generate type probes for every element     |
| `type-bench`          | `dialecte bench`         | measure instantiations, WRITE the baseline |
| `type-bench:check`    | `dialecte bench --check` | CI gate: > 5 % growth over baseline fails  |
| `type-narrowing`      | `dialecte narrowing`     | schema-derived narrowing still holds       |
| `type-audit`          | `dialecte audit`         | readability of emitted types               |

Careful: before `@dialecte/cli` 0.2.0, `dialecte bench --help` is not a help flag - it runs the bench
and writes the baseline (from 0.2.0 it only prints the help). Bench single-threaded (the package's bench tsconfig) for order-stable counts. A gate
breach is a prompt to explain the growth; re-baseline in its own lot when it is legitimate.

## Retro gate - before you hand over

List in your hand-over every place where this skill was wrong, missing or misleading for the task,
and every correction the user made that a skill should have prevented. Then:

- **Inside a dialecte repository**: fix the skill page in the same change (skills ship with the
  package that owns the code) and run `npm run skills:generate`, then
  `npm run skills:check`.
- **In an app**: draft an issue for the package that ships the skill - the statement that was wrong
  or missing, the evidence (file, behaviour), the wording you propose - and show it to the user.
  Post it only with their approval.
- Nothing to report: write "skill retro: nothing".
