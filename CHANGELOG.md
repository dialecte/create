# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.4] - 2026-09-28

### Added

- A scaffolded package ships a worked example written with its schema's own elements: a query (`sayHello`) and a transaction (`ensure<Child>`), each with a table-driven test.
- The definition describes types and structure: `type` on attributes and text, `contentModel`, `nillable`, `anyNamespace`, text `default` / `fixed`.
- An element declared differently under different parents keeps each declaration on that parent's edge (`children.details[child]`), read by `resolveDefinition` in `@dialecte/core`.
- `ATTRIBUTES.byParent`: the attributes of a child as declared under each parent, so `addChild` rejects an attribute its parent does not allow.
- `--root <element>` on `create` and `generate`, for a schema where several elements can start a document.
- `-v` / `--version`.

### Changed

- A scaffolded package targets `@dialecte/core` `^0.5.0`; regenerate an existing definition to use it.
- `ATTRIBUTES` is `{ byTag, byParent }`: read `ATTRIBUTES.byTag[tag]` where you read `ATTRIBUTES[tag]`.
- Generated files come out formatted with the project's own formatter.
- The default namespace is the schema's `targetNamespace`, or none when the schema declares none.
- A scaffolded package runs its tests out of the box (Playwright pinned, browser installed before `npm test`).
- The project factory of a scaffolded package accepts `dev`, e.g. `{ perf: true }`.

### Removed

- `children.choices`: choice groups are the `choice` nodes of `contentModel`.

### Fixed

- Identity fields match the schema's keys: no longer borrowed by the elements on a key's path, and wildcard keys now count.
- Substitution groups are resolved: members appear under their head's parents, abstract heads are gone.
- The root is never guessed: several candidates are refused until `--root` picks one.
- An element declared several times is no longer reduced to its first declaration.
- Element names that are not TypeScript identifiers (`boolean-value`) and values holding a quote produce files that compile.
- Extension methods are typed on a document opened from a project.
- The `type-check` script of a scaffolded package actually checks the code.
- `npm install` no longer fails in a freshly scaffolded package.
- A failed scaffold removes what it wrote.
- The default namespace is no longer read from a commented-out schema tag.
- Generating twice in one process works; a flag value starting with a dash is read as a value.

## [0.0.3] - 2026-07-06

### Changed

- Attribute keying is now predictable: an attribute in the element's own (default) namespace is keyed by its bare local name; any non-default-namespace attribute is always keyed `prefix:local` (e.g. `xsi:type`). This replaces qualify-on-collision, which only added a prefix when two attributes on an element shared a local name. Regenerating a dialect yields collision-safe, stable attribute keys — a prefixed non-default name can never clash with a bare default one — but a consumer that read a non-default attribute by its bare local name must switch to the prefixed name.

### Added

- Per-parent-context element namespaces: the generated definition now carries a namespace on a parent→child edge (`ChildDefinition.namespace`) when the child's declaring-schema namespace differs from the element's canonical one, so a local element name declared in more than one namespace serializes correctly under each parent. Emitted sparsely — only genuine overrides — and consumed by `@dialecte/core`'s `standardizeRecord` (falling back to the element's own namespace).

## [0.0.2] - 2026-06-26

### Added

- Generated dialects now ship `@dialecte/cli` (devDep + coverage / bench / narrowing / audit scripts), the `_type-perf.yml` gate workflow, and `.gitignore` entries for the throwaway probes.
- Repo dev tooling: `husky` pre-commit running `oxlint` + `oxfmt` (`npm run check`), plus this CHANGELOG.

### Changed

- Scaffolded `vite.config.ts` externalizes `@dialecte/core` + `dexie` (no longer bundled).

## [0.0.1] - 2026-06-16

### Added

- Initial release: `@dialecte/create` scaffolds and generates Dialecte SDKs from an
  XSD schema, running the Python generator in WebAssembly (no local Python required).
