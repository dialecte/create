# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Each declaration names its declared type in `type` (its Clark name) when the type is named: an instance may name that type with `xsi:type` too, besides its `variants`.

### Changed

- **Breaking (generated types):** an element that may take another type with `xsi:type` gets a union of attribute types on `'xsi:type'` instead of one type with an open hint. Its own member has its attributes, with `'xsi:type'` naming its own type or absent (no own member for an abstract type: an instance names one of the others); each type it may take has its member `AttributesType_<type>`, `'xsi:type'` required. Each literal is the value core stores: the local name in the default namespace, `prefix:local` in another. Reading an attribute only some types have now needs a check of `'xsi:type'` first. Elements without such types are generated as before.
- **Breaking (CLI):** `create --namespace` is removed. The default namespace is the root element's, which the generated `xsi:type` values and the scaffold's namespaces check rely on; any other made a package that failed its own test.
- A flag a command does not take is refused by name instead of ignored.
- `OptionalAttributeNames` lists the attributes of every member of a union, not only those all members share.
- A scaffolded package declares in its `namespaces` config every namespace the definition gives a prefix, and a test checks the config still agrees with the definition (default namespace, prefixes): core stores `xsi:type` values with the config's prefixes, the types with the definition's.
- `--root` takes any global element of the schema, also one another element holds: a schema whose every element is held by another (FHIR) can now be generated. The automatic choice is unchanged.

### Fixed

- Two types sharing a local name in two namespaces no longer get the same `xsi:type` value in the types (`'tA'` twice): the one outside the default namespace is `'prefix:tA'`.
- An element reached only through a type an element of `xs:anyType` may take no longer lists that element as its parent: such an element admits any content, so the parent and child tables now agree (it held no child either).

## [0.1.0] - 2026-10-12

### Changed

- **Breaking:** The generator is rebuilt: it reads any XSD 1.0 schema and writes the definition `@dialecte/core` 0.6 reads, so regenerate your dialecte.
- **Breaking:** A tag declared several ways keeps each declaration, attributes and text carry their facets in their datatype, and identity constraints sit on the declaration that declares them.
- The generated `TYPES` lists the types an element may take with `xsi:type`, and the generated attribute types offer `xsi:type` where an element may name one.
- For a tag declared several ways, the by-tag attribute type hints the values any of its declarations accepts.
- A scaffolded package targets `@dialecte/core` `^0.6.0` and wires `TYPES` into its config and its XML assertions.

### Fixed

- A substitution group member whose type derives by a method its head, or a type on the way, blocks no longer stands for the head; if that leaves several possible roots, choose one with `--root`.
- The members of a member that blocks substitution stand for the head again.
- An element of `anyType` no longer offers `xs:anySimpleType` and `xs:anyAtomicType` as `xsi:type` types in a schema that imports the XML namespace.

## [0.0.7] - 2026-09-29

### Fixed

- `npm create @dialecte`, `npx @dialecte/create` and a scaffolded package's `npm run generate` do something: run through npm's bin link, the CLI used to exit without a word.

## [0.0.6] - 2026-09-29

### Added

- A scaffolded package checks every test fixture against its schema before the suite runs: a mistyped tag, a wrong namespace or an unknown attribute fails with a clear message.

### Fixed

- The default namespace of a scaffolded package is its root element's: an extension schema (IEC 61850-6-100 over SCL) used to give the extension's namespace to every document.

## [0.0.5] - 2026-09-29

### Changed

- A scaffolded package uses `@dialecte/cli` 0.0.3: its type bench measures the package's own types, library declarations skipped.

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
