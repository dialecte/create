/**
 * CLI smoke test: run the WASM generator against a minimal fixture XSD and
 * assert the three definition files are produced. Exercises the full Pyodide
 * pipeline offline. Exits non-zero on failure.
 *
 * Usage: node scripts/smoke.mjs   (run after `npm run build` and `npm run vendor`)
 */
import { mkdtemp, rm, stat, readFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { runGenerator } from '../dist/cli/index.js'

const FIXTURE = new URL('../test/fixtures/minimal.xsd', import.meta.url).pathname
const EXPECTED = ['definition.generated.ts', 'constants.generated.ts', 'types.generated.ts']

async function main() {
	const outDir = await mkdtemp(join(tmpdir(), 'dialecte-smoke-'))
	try {
		await runGenerator({ entry: FIXTURE, outDir, quiet: true })

		for (const file of EXPECTED) {
			const path = join(outDir, file)
			const info = await stat(path)
			if (!info.isFile() || info.size === 0) {
				throw new Error(`Missing or empty output: ${file}`)
			}
		}

		const constants = await readFile(join(outDir, 'constants.generated.ts'), 'utf8')
		if (!constants.includes('Root') || !constants.includes('Item')) {
			throw new Error('Generated constants missing expected element names')
		}

		console.log('Smoke test passed: 3 files generated with expected elements.')
	} finally {
		await rm(outDir, { recursive: true, force: true })
	}
}

main().catch((err) => {
	console.error(`Smoke test failed: ${err instanceof Error ? err.message : String(err)}`)
	process.exit(1)
})
