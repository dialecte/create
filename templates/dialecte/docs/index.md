# **packageName**

Dialecte SDK for `__dialecteId__`, generated with [`@dialecte/create`](https://github.com/dialecte/create).

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

## Test

The tests run in two tiers (`vitest.config.ts`):

```sh
npm run test:node          # every test in node, on the in-memory store (the default tier)
npm run test:browser       # the browser-only tests in Chromium (none in a new package)
npm test                   # test:node, then test:browser
npm run test:browser:all   # the whole suite in Chromium, on the local store (CI, before a merge)
```

A test file that needs a browser API (OPFS, a worker, real IndexedDB, the page's `DOMParser`, a download) goes in
`BROWSER_ONLY_TEST_FILES` of `vitest.config.constants.ts`, `{ path, why }`, the `why` naming that API; one that
reads the package from disk or starts node goes in `NODE_ONLY_TEST_FILES`. No test names its store: the `node`
project's setup (`src/__version__/test/in-memory-storage.setup.ts`) selects the in-memory one.

### Using the test helpers in your own package

`run__DialecteName__TestCases` and `create__DialecteName__TestProject` (from `__packageName__/__version__/test`)
open their projects on the store the test runner chose. To run your tests in node, depend on `@dialecte/core`
yourself and give your node vitest project a setup file with the same line:

```ts
// in-memory-storage.setup.ts, in setupFiles of your node vitest project
import { useTestStorage } from '@dialecte/core/test'

useTestStorage({ type: 'inMemory' })
```

A project the helpers open inside a running test (its body or a `beforeEach`) is destroyed when that test ends.
One opened outside a running test (in `beforeAll`, to keep it across tests) is yours to destroy, in `afterAll`.
