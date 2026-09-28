# **packageName**

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

## Extend

`src/__version__/extensions/hello-world/` is a worked example, written with the elements of this
schema: a query and a table-driven test next to it, written with the runners of
`src/__version__/test` (`withoutExport` for a read, `withExport` for a write checked as XML with
XPath, `generic` for a pure function).
<!-- __ifExampleChild__ -->

A transaction ensures a `__exampleChild__` under the `__exampleRoot__`, tested the same way.
<!-- __endIfExampleChild__ -->

Copy its shape for a module of your own, then delete the folder and its line in
`src/__version__/extensions/index.ts`.

```ts
const doc = await project.openDocument(id)
const greeting = await doc.query.helloWorld.sayHello()
// __ifExampleChild__
await doc.transaction((tx) => tx.helloWorld.ensure__ExampleChild__())
// __endIfExampleChild__
```

## Regenerate definitions

The element definitions in `src/__version__/definition/` are generated from an XSD schema.
To regenerate after a schema change:

```sh
npm run generate -- ./path/to/schema.xsd
```

The script carries the options this package was generated with (its root element, when the
schema offers several), so a regeneration reproduces the same definition.

## Develop

```sh
npm install
npm run build        # type-check + bundle (ESM + d.ts)
npm test             # vitest (browser)
npm run doc:dev      # vitepress docs
```
