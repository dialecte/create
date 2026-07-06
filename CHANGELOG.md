# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
