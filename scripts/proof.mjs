/**
 * The generator's proof, one command: every tier that has its input, in order, with a table of what ran.
 *
 *   npm run proof
 *   PROOF_REQUIRE=iec,corpora npm run proof     a tier named here and skipped fails the run
 *
 * self     no network: check, the TypeScript and Python suites (oracles, construct inventory, determinism,
 *          committed instances, a fixed range of generated schemas), and the CLI smoke test (the committed fixtures regenerate byte-identical through
 *          the engine the CLI ships - needs `npm run vendor` once)
 * iec      local: the five dialectes' committed constants and types derive byte-identical from their committed
 *          definitions (the sibling repositories beside create, or in $DIALECTE_ROOT)
 * corpora  the sources the licence review admitted (python/corpora/manifest.json, fetched by
 *          `npm run corpora:fetch` into .corpora/): every schema-tier check on every schema, and the instance tier
 *          (every labelled instance, then sampled structural edits of it, predicted from the definition and judged
 *          by libxml2; PROOF_FULL=1 runs every edit), a few minutes
 *
 * The mutation gate is its own command (`npm run mutants`): minutes, not seconds, run before a generator change is
 * committed. Exit 1 on any failure or on a required tier skipped.
 */
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const CREATE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DIALECTE_ROOT = resolve(process.env.DIALECTE_ROOT ?? join(CREATE_ROOT, '..'))
const CORPORA_ROOT = resolve(process.env.DIALECTE_CORPORA_DIR ?? join(CREATE_ROOT, '.corpora'))
const REQUIRED = new Set(
	(process.env.PROOF_REQUIRE ?? '')
		.split(',')
		.map((tier) => tier.trim())
		.filter(Boolean),
)

/** The committed definitions derive-check reads (scripts/derive-check/derive-check.ts). */
const IEC_DEFINITIONS = [
	'core/src/test/generated',
	'scl/src/v2019C1/definition',
	'nsd/src/v2017A/definition',
	'plc/src/v1/definition',
	'plc/src/tc6-v201/definition',
]

/** Each step: its tier, its name, the npm script it runs, and why it is skipped when its input is absent. */
const STEPS = [
	{ tier: 'self', name: 'check (types, lint, format)', script: 'check' },
	{ tier: 'self', name: 'TypeScript suite', script: 'test:ts' },
	{ tier: 'self', name: 'Python suite', script: 'test:py' },
	{ tier: 'self', name: 'CLI smoke + fixture regeneration', script: 'test:cli' },
	{
		tier: 'self',
		name: 'generated schemas (300 draws)',
		script: 'fuzz',
		args: ['--seed', 'proof', '--count', '300'],
	},
	{
		tier: 'iec',
		name: 'five dialectes derive byte-identical',
		script: 'derive:check',
		// derive-check skips an absent dialecte and passes: the tier runs only when it would check all five
		absent: () => {
			const missing = IEC_DEFINITIONS.filter((folder) => !existsSync(join(DIALECTE_ROOT, folder)))
			return missing.length === 0 ? undefined : `absent in ${DIALECTE_ROOT}: ${missing.join(', ')}`
		},
	},
	{
		tier: 'corpora',
		name: 'admitted corpora, schema and instance tiers',
		script: 'test:corpora',
		absent: () =>
			existsSync(join(CORPORA_ROOT, 'manifest.lock.json'))
				? undefined
				: `nothing fetched in ${CORPORA_ROOT} (npm run corpora:fetch)`,
	},
]

const rows = []
let failed = false
for (const step of STEPS) {
	const reason = step.absent?.()
	if (reason !== undefined) {
		const required = REQUIRED.has(step.tier)
		if (required) failed = true
		rows.push([step.tier, step.name, required ? 'SKIPPED, REQUIRED' : 'skipped', reason])
		continue
	}
	process.stdout.write(`\n== ${step.tier}: ${step.name} (npm run ${step.script})\n`)
	const started = Date.now()
	const args = step.args === undefined ? [] : ['--', ...step.args]
	const run = spawnSync('npm', ['run', '-s', step.script, ...args], {
		cwd: CREATE_ROOT,
		stdio: 'inherit',
		env: { ...process.env, DIALECTE_ROOT },
	})
	const seconds = `${((Date.now() - started) / 1000).toFixed(1)} s`
	if (run.status !== 0) failed = true
	rows.push([step.tier, step.name, run.status === 0 ? 'passed' : 'FAILED', seconds])
}

const widths = [0, 1, 2].map((column) => Math.max(...rows.map((row) => row[column].length)))
process.stdout.write('\nGenerator proof\n')
for (const row of rows) {
	process.stdout.write(
		`  ${row
			.slice(0, 3)
			.map((cell, column) => cell.padEnd(widths[column]))
			.join('  ')}  ${row[3]}\n`,
	)
}
process.stdout.write(failed ? 'proof: FAILED\n' : 'proof: green\n')
process.exit(failed ? 1 : 0)
