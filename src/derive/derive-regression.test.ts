import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import {
	copyFileSync,
	mkdtempSync,
	readdirSync,
	readFileSync,
	rmSync,
	writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { deriveRoot } from './derive-root.ts'
import { emitConstantsSource } from './emit-constants.ts'
import { emitTypesSource } from './emit-types.ts'

// Dialectes committed with the files the generator wrote for them (core's own test dialecte, and a
// schema written for these tests: a homonym, an element without attributes): the derivation must
// reproduce them byte for byte once formatted. Each fixture's `.oxfmtrc.json` is its formatting
// reference, applied with this package's oxfmt; a layout change of a future oxfmt shows here first.
const CREATE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const FIXTURES = join(CREATE_ROOT, 'test/fixtures/definition')

for (const fixture of readdirSync(FIXTURES).sort()) {
	describe(`derivation of the committed dialecte ${fixture}`, async () => {
		const folder = join(FIXTURES, fixture)
		const { DEFINITION } = await import(pathToFileURL(join(folder, 'definition.generated.ts')).href)
		const root = deriveRoot({ definition: DEFINITION })
		const formatted = format({
			folder,
			files: {
				'constants.generated.ts': emitConstantsSource({ definition: DEFINITION, root }),
				'types.generated.ts': emitTypesSource({ definition: DEFINITION }),
			},
		})

		for (const [file, text] of Object.entries(formatted)) {
			it(`${fixture} -> ${file} as committed`, () => {
				assert.equal(text, readFileSync(join(folder, file), 'utf-8'))
			})
		}
	})
}

function format(params: {
	folder: string
	files: Readonly<Record<string, string>>
}): Record<string, string> {
	const { folder, files } = params
	const scratch = mkdtempSync(join(tmpdir(), 'derive-regression-'))
	try {
		copyFileSync(join(folder, '.oxfmtrc.json'), join(scratch, '.oxfmtrc.json'))
		for (const [file, text] of Object.entries(files)) writeFileSync(join(scratch, file), text)
		const oxfmt = join(CREATE_ROOT, 'node_modules', '.bin', 'oxfmt')
		const run = spawnSync(oxfmt, Object.keys(files), { cwd: scratch, encoding: 'utf-8' })
		if (run.status !== 0) throw new Error(`oxfmt failed: ${run.stderr}`)
		return Object.fromEntries(
			Object.keys(files).map((file) => [file, readFileSync(join(scratch, file), 'utf-8')]),
		)
	} finally {
		rmSync(scratch, { recursive: true, force: true })
	}
}
