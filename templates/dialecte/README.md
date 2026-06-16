# __packageName__

Dialecte SDK for `__dialecteId__`.

Built on [`@dialecte/core`](https://github.com/dialecte/core) and scaffolded with
[`@dialecte/create`](https://github.com/dialecte/create).

## Install

```sh
npm install __packageName__ @dialecte/core
```

## Usage

```ts
import { create__DialecteName__Project } from '__packageName__/__version__'

const project = create__DialecteName__Project()
await project.open('my-project')
```

## Regenerate definitions

The element definitions in `src/__version__/definition/` are generated from an XSD schema.
To regenerate after a schema change:

```sh
npm create @dialecte generate -- --entry ./path/to/schema.xsd --out-dir ./src/__version__/definition
```

## Develop

```sh
npm install
npm run build        # type-check + bundle (ESM + d.ts)
npm test             # vitest (browser)
npm run doc:dev      # vitepress docs
```
