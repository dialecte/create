import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

const RUNNER = fileURLToPath(new URL('./run-tests.ts', import.meta.url))
/** A fixture suite of this folder, by file name. */
function fixture(name: string): string {
	return fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url))
}

describe('run-tests', () => {
	it('a suite that throws while it is built -> the run fails (node --test alone exits 0)', () => {
		const run = spawnSync('node', [RUNNER, 'files', fixture('broken-suite.fixture.ts')], {
			encoding: 'utf-8',
		})
		assert.notEqual(run.status, 0)
	})

	it('passing suites -> the run passes', () => {
		const run = spawnSync('node', [RUNNER, 'files', fixture('passing-suite.fixture.ts')], {
			encoding: 'utf-8',
		})
		assert.equal(run.status, 0)
	})
})
