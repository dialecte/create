# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
