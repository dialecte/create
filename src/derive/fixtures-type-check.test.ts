import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

// The generated files of every committed dialecte compile on their own under the strictest options a
// consumer may turn on: a definition, constants or types file a package cannot compile is never shipped.
const CREATE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const FIXTURES = join(CREATE_ROOT, 'test/fixtures/definition')
const TSC = join(CREATE_ROOT, 'node_modules', '.bin', 'tsc')
const STRICTEST = [
	'--noEmit',
	'--strict',
	'--target',
	'ES2022',
	'--module',
	'ESNext',
	'--moduleResolution',
	'Bundler',
	'--noUnusedLocals',
	'--noUnusedParameters',
	'--exactOptionalPropertyTypes',
	'--noUncheckedIndexedAccess',
	'--noPropertyAccessFromIndexSignature',
]

// directories only: a stray file (a .DS_Store) is no fixture
const FIXTURE_NAMES = readdirSync(FIXTURES, { withFileTypes: true })
	.filter((entry) => entry.isDirectory())
	.map((entry) => entry.name)
	.sort()

describe('the generated files of the committed dialectes type-check', () => {
	for (const fixture of FIXTURE_NAMES) {
		it(`${fixture} compiles under the strictest options`, () => {
			const folder = join(FIXTURES, fixture)
			const files = readdirSync(folder)
				.filter((file) => file.endsWith('.generated.ts'))
				.map((file) => join(folder, file))
			assert.equal(files.length, 3)
			const run = spawnSync(TSC, [...STRICTEST, ...files], { encoding: 'utf-8' })
			assert.equal(run.status, 0, run.stdout)
		})
	}
})
