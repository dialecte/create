# @dialecte/create

Scaffold and generate [Dialecte](https://github.com/dialecte) SDKs from an XSD schema.

The XSD-to-TypeScript generator is written in Python but runs inside Node via
[Pyodide](https://pyodide.org/) (WebAssembly), so **end users do not need Python
installed**. Pure-Python dependencies are vendored as wheels and installed
offline at runtime.

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

| Option                 | Default                        | Description                                         |
| ---------------------- | ------------------------------ | --------------------------------------------------- |
| `--name <pkg>`         | `@dialecte/<schema basename>`  | npm package name                                    |
| `--out <dir>`          | `./<dialecte id>`              | target directory                                    |
| `--version <vN>`       | `v1`                           | version folder name                                 |
| `--namespace <uri>`    | the schema's `targetNamespace` | default XML namespace URI                           |
| `--core-version <ver>` | `^0.5.0`                       | `@dialecte/core` version range                      |
| `--root <element>`     | the one root candidate         | which element starts a document, when several could |

The generated package includes:

- Hydrated type aliases bound to your config (`Dialecte.Project`, `Dialecte.Query`, ...)
- A project factory (`create<Name>Project`)
- Test hydration utilities wired to `@dialecte/core/test`: the three table-driven runners
  (`generic`, `withoutExport`, `withExport`)
- A `helloWorld` extension - one query, one transaction, their tests - that runs green against the
  schema you gave, as a worked example to copy from and then delete
- VitePress documentation scaffolding

The default namespace is read from the schema: its `targetNamespace`, or none at all for a schema
that declares none. After `npm install`, run `npm run format:fix` once - names of any length are
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

The generator engine is a Python package under `python/`. Develop and test it
with native Python (fast loop), then ship it to users via WebAssembly.

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

`npm run test:cli` builds and runs the smoke test: generation, scaffolds and their files, flags.
`npm run test:cli:install` also installs a scaffolded package and type-checks it against the
engine it targets; set `DIALECTE_CORE=../core` (a checkout, or a `.tgz`) to check against an
unreleased engine.

`xsd/` and `local/` are git-ignored: they hold local-only schemas and the
maintainer's batch generation script.
