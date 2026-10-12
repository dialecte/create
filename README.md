# @dialecte/create

Scaffold and generate [Dialecte](https://github.com/dialecte) SDKs from an XSD schema.

The XSD reader is written in Python but runs inside Node via
[Pyodide](https://pyodide.org/) (WebAssembly), so **end users do not need Python
installed**. Pure-Python dependencies are vendored as wheels and installed
offline at runtime. It writes the definition - every element declaration of the schema, its values
with their facets, identity constraints and the types an element may take with `xsi:type` (`TYPES`);
the constants and types are derived from it in TypeScript.

## Quick start

Scaffold a brand-new dialecte package from a schema:

```sh
npm create @dialecte -- ./my-schema.xsd --name @acme/widget
```

> `npm create @dialecte` resolves to the `@dialecte/create` package. The `--`
> separator is required so npm forwards the schema path and flags to the CLI
> instead of consuming them itself.

Or just regenerate definition files into an existing package:

```sh
npx @dialecte/create generate --entry ./my-schema.xsd --out-dir ./src/v1/definition
```

## Commands

### `create <schema.xsd>`

Scaffolds a new dialecte package (built on `@dialecte/core`) and generates its
element definitions from the schema in one step.

| Option                 | Default                       | Description                                         |
| ---------------------- | ----------------------------- | --------------------------------------------------- |
| `--name <pkg>`         | `@dialecte/<schema basename>` | npm package name                                    |
| `--out <dir>`          | `./<dialecte id>`             | target directory                                    |
| `--version <vN>`       | `v1`                          | version folder name                                 |
| `--namespace <uri>`    | the root element's namespace  | default XML namespace URI                           |
| `--core-version <ver>` | `^0.6.0`                      | `@dialecte/core` version range                      |
| `--root <element>`     | the one root candidate        | which element starts a document, when several could |

The generated package includes:

- Hydrated type aliases bound to your config (`Dialecte.Project`, `Dialecte.Query`, ...)
- A project factory (`create<Name>Project`)
- Test hydration utilities wired to `@dialecte/core/test`: the three table-driven runners
  (`generic`, `withoutExport`, `withExport`)
- A `helloWorld` extension - one query, one transaction, their tests - that runs green against the
  schema you gave, as a worked example to copy from and then delete
- VitePress documentation scaffolding

The default namespace is the one the root element lives in, or none for a schema without one. For
an extension schema (IEC 61850-6-100 over SCL) that is the base schema's namespace, not the entry's. After `npm install`, run `npm run format:fix` once - names of any length are
substituted into the template, so its line breaks cannot suit every package.

### `generate`

Generates only the three definition files
(`definition.generated.ts`, `constants.generated.ts`, `types.generated.ts`), formatted with the
oxfmt of the project they land in when one is installed (its own copy otherwise), so that
regenerating shows the schema change and nothing else.

| Option                 | Description                                         |
| ---------------------- | --------------------------------------------------- |
| `--root <element>`     | which element starts a document, when several could |
| `--entry <schema.xsd>` | entry XSD file (required)                           |
| `--out-dir <dir>`      | output directory (required)                         |

## Bring your own XSD

This package does **not** bundle IEC or other proprietary schemas. Point it at
your own `.xsd` file. Optional sidecar files next to the entry XSD are honored:

- `parent-mapping.json` - declares parents for orphan (wildcard) elements
- `attribute-mapping.json` - injects extension-namespace attributes

## Development

The schema reader is a Python package under `python/generate`. Develop and test it
with native Python (fast loop), then ship it to users via WebAssembly; `src/derive` derives the
constants and types from the definition it writes.

```sh
# Engine (Python) tests - python/.venv when present, python3 otherwise
npm run test:py

# Vendor the runtime wheels (network required; run once / on dep bump)
npm run vendor

# Build the Node CLI
npm run build

# Try it
node dist/cli/index.js generate --entry ./xsd/SCL/IEC61850-6-100.xsd --out-dir .tmp/out
```

The TypeScript side runs its `.ts` files directly with Node (type stripping), so the development
scripts need **Node 22.18 or later** (the published CLI is bundled and runs on Node 20):

```sh
npm run test:ts          # unit tests of src/ and scripts/ (node:test)
npm run derive:check     # constants and types derived from the committed definitions of the sibling dialectes
npm run definition:diff -- <before.generated.ts> <after.generated.ts>   # semantic difference of two definitions
```

`npm run test:cli` builds and runs the smoke test: generation, scaffolds and their files, flags.
`npm run test:cli:install` also installs a scaffolded package and type-checks it against the
engine it targets; set `DIALECTE_CORE=../core` (a checkout, or a `.tgz`) to check against an
unreleased engine.

### Proving the generator

`npm run proof` runs every check of the generator that has its input and prints what ran. Without
network it checks types, lint and format, runs both suites with their libxml2 oracles and the
construct inventory, and regenerates the committed fixtures through the shipped engine
(`test/fixtures/xsd`, among them a torture schema that writes every construct the generator reads).
With the sibling dialectes checked out beside `create` (or in `$DIALECTE_ROOT`) it also derives
their constants and types. `PROOF_REQUIRE=iec` makes a skipped tier fail.

`npm run mutants [module ...]` changes the generator's code one point at a time and runs the suite on
each change, in copies of the package. A change no test notices must be listed in
`python/mutants/records/` with the reason it cannot alter any output; `--record` writes the new ones
with an empty reason to fill. Run it before committing a change to `python/generate`: it takes the
better part of an hour on the whole generator, less on the modules named.

`npm run corpora:fetch` downloads the third-party corpora the licence review admitted (plan 10b of the
validation plans), each pinned by sha256, into `.corpora/` (never committed); `npm run test:corpora` then runs
every schema-tier check on every schema they hold - the generator reads it, its definition reads back, its
constructs are classified, its patterns, identity paths, `xsi:type` variants and attribute wildcards agree with
libxml2, and the facts the documents declare are kept. A disagreement a reviewed reason explains is listed in
`python/corpora/known-exceptions.json`; a listed one that stops occurring fails too. `npm run fuzz -- --seed S
--count N` judges generated schemas the same way, a fixed range of them with every `npm run test:py`.

A construct of XSD the generator has never been shown to read fails the suite: every construct a
schema writes is classified in `python/proof/constructs.json` as handled, excluded with the reason, or
XSD 1.1.

`xsd/` and `local/` are git-ignored: they hold local-only schemas and the
maintainer's batch generation script.
