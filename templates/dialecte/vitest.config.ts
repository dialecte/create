import { globSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import viteConfig from './vite.config.ts'
import { BROWSER_ONLY_TEST_FILES, NODE_ONLY_TEST_FILES } from './vitest.config.constants.ts'

import { playwright } from '@vitest/browser-playwright'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'

import type { DeclaredTestFile } from './vitest.config.types.ts'

const ROOT = fileURLToPath(new URL('./', import.meta.url))
/** Every unit test file of the package. */
const UNIT_TESTS = ['src/**/*.test.{js,ts,jsx,tsx}']
/** The tier projects: node (the default), the browser-only list, and the whole suite in the browser. */
const NODE_PROJECT = 'node'
const BROWSER_PROJECT = 'browser'
const BROWSER_ALL_PROJECT = 'browser-all'
/** The setup of the `node` project: the test helpers open their projects on the in-memory store. */
const IN_MEMORY_STORAGE_SETUP = 'src/__version__/test/in-memory-storage.setup.ts'

/** Every path of a tier-only list names a file: a moved test file must not drop out of its tier unseen. */
function pathsOf(params: { project: string; files: readonly DeclaredTestFile[] }): string[] {
	const { project, files } = params
	const paths = files.map(function pathOf(file) {
		return file.path
	})
	const missing = paths.filter(function namesNoFile(path) {
		return globSync(path, { cwd: ROOT }).length === 0
	})
	if (missing.length > 0) {
		throw new Error(
			`vitest project "${project}" lists files that do not exist: ${missing.join(', ')}`,
		)
	}
	return paths
}

const browserOnlyPaths = pathsOf({ project: BROWSER_PROJECT, files: BROWSER_ONLY_TEST_FILES })
const nodeOnlyPaths = pathsOf({ project: BROWSER_ALL_PROJECT, files: NODE_ONLY_TEST_FILES })

/** Headless Chromium, one per project: vitest names the instance after the project it belongs to. */
function headlessChromium() {
	return {
		provider: playwright(),
		enabled: true,
		headless: true,
		instances: [{ browser: 'chromium' as const }],
		screenshotFailures: false,
	}
}

export default mergeConfig(
	viteConfig,
	defineConfig({
		test: {
			watch: false,
			testTimeout: 5_000,
			projects: [
				{
					// every unit test file but the browser-only ones, in node on the in-memory store; the files share
					// their modules
					resolve: viteConfig.resolve,
					plugins: [],
					test: {
						name: NODE_PROJECT,
						environment: 'node',
						isolate: false,
						include: UNIT_TESTS,
						exclude: [...configDefaults.exclude, ...browserOnlyPaths],
						root: ROOT,
						setupFiles: [IN_MEMORY_STORAGE_SETUP],
					},
				},
				{
					// the browser-only test files, on the local store
					resolve: viteConfig.resolve,
					plugins: [],
					test: {
						name: BROWSER_PROJECT,
						browser: headlessChromium(),
						include: browserOnlyPaths,
						root: ROOT,
					},
				},
				{
					// the whole suite in the browser, on the local store: the run before a branch merges
					resolve: viteConfig.resolve,
					plugins: [],
					test: {
						name: BROWSER_ALL_PROJECT,
						browser: headlessChromium(),
						include: UNIT_TESTS,
						exclude: [...configDefaults.exclude, ...nodeOnlyPaths],
						root: ROOT,
					},
				},
			],
		},
	}),
)
