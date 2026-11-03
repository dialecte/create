import type { DeclaredTestFile } from './vitest.config.types.ts'

/**
 * The test files that need a browser API (`navigator.storage`, OPFS, a worker, real IndexedDB, the page's
 * `DOMParser`, a download): the `browser` project runs them, the `node` project leaves them out. Every other test
 * file runs in node, on the in-memory store. An entry is `{ path, why }`, the `why` naming that API. Empty: no test
 * of this package needs a browser.
 */
export const BROWSER_ONLY_TEST_FILES: readonly DeclaredTestFile[] = []

/**
 * The test files that read the package from disk or start node (`node:fs`, `node:child_process`): the
 * `browser-all` project leaves them out. An entry is `{ path, why }`, the `why` naming that node API. Empty: no test
 * of this package needs node.
 */
export const NODE_ONLY_TEST_FILES: readonly DeclaredTestFile[] = []
