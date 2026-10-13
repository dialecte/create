/**
 * `node scripts/test-runner/run-tests.ts all|fast|full|files <path>...`: create's TypeScript tests under `node --test`,
 * failing on every failure node reports. Node 24 prints a suite whose `describe` callback throws as failing, then
 * exits 0 with `# fail 0`; the TAP stream still says `not ok`, so this runner reads it.
 * - `all`: every test of `src` and `scripts` (`npm run test:ts`);
 * - `fast` / `full`: the derive and oracle tests the TypeScript mutation gate runs on a mutant - `fast` without the
 *   two `tsc --strict` suites, `full` with them;
 * - `files`: the paths given.
 */
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const CREATE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
/** The suites that type-check with tsc: the slow ones. */
const TYPE_CHECKING = ['fixtures-type-check.test.ts', 'type-probes.test.ts']
const GATED_FOLDERS = ['src/derive', 'scripts/derive-oracle']

function filesOf(params: { mode: string; paths: readonly string[] }): string[] {
	const { mode, paths } = params
	if (mode === 'files') return [...paths]
	if (mode === 'all') return ['src/**/*.test.ts', 'scripts/**/*.test.ts']
	if (mode !== 'fast' && mode !== 'full')
		throw new Error('usage: run-tests.ts all|fast|full|files <path>...')
	return GATED_FOLDERS.flatMap((folder) =>
		readdirSync(join(CREATE_ROOT, folder))
			.filter((file) => file.endsWith('.test.ts'))
			.filter((file) => mode === 'full' || !TYPE_CHECKING.includes(file))
			.map((file) => join(folder, file)),
	)
}

function main(): number {
	const [mode = '', ...paths] = process.argv.slice(2)
	const files = filesOf({ mode, paths })
	const scratch = mkdtempSync(join(tmpdir(), 'run-tests-'))
	const tap = join(scratch, 'report.tap')
	try {
		// the readable report for people, the TAP one for the verdict
		const run = spawnSync(
			'node',
			[
				'--test',
				'--test-reporter=spec',
				'--test-reporter-destination=stdout',
				'--test-reporter=tap',
				`--test-reporter-destination=${tap}`,
				...files,
			],
			// a run of its own, even started from inside a test: no parent test context
			{ cwd: process.cwd(), stdio: 'inherit', env: withoutTestContext() },
		)
		const notOk = readFileSync(tap, 'utf-8')
			.split('\n')
			.filter((line) => /^\s*not ok\b/.test(line))
		if (notOk.length > 0 && run.status === 0) {
			process.stderr.write(
				`run-tests: node reported success, its TAP says otherwise:\n${notOk.join('\n')}\n`,
			)
		}
		return notOk.length > 0 ? 1 : (run.status ?? 1)
	} finally {
		rmSync(scratch, { recursive: true, force: true })
	}
}

function withoutTestContext(): NodeJS.ProcessEnv {
	const { NODE_TEST_CONTEXT: _parent, ...env } = process.env
	return env
}

process.exit(main())
