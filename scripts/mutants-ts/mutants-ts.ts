/**
 * `npm run mutants:ts [-- <file>... ] [-- --record]`: the mutation gate of create's TypeScript side (src/derive),
 * the twin of `npm run mutants` for the Python generator. StrykerJS changes the code one point at a time and runs the
 * derive and oracle tests on each change - first without the slow tsc suites, then with them on the survivors only
 * (`scripts/test-runner/run-tests.ts`); every change no test notices must be listed in
 * `scripts/mutants-ts/records/<file>.json` with the reason it cannot alter any output. `--record` writes the new
 * ones with an empty reason to fill and drops the listed ones that no longer survive. Local gate, not CI: minutes.
 */
import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { judgeReport, survivorRanges, withFullRun } from './judge.ts'

import type { MutationReport, RecordedSurvivor, SurvivorRecords } from './mutants-ts.types.ts'

const CREATE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const RECORDS = join(CREATE_ROOT, 'scripts', 'mutants-ts', 'records')
const REPORT = join(CREATE_ROOT, '.tmp', 'stryker', 'report.json')
const FULL_REPORT = join(CREATE_ROOT, '.tmp', 'stryker', 'report-full.json')

function main(): number {
	const args = process.argv.slice(2)
	const record = args.includes('--record')
	const files = args.filter((arg) => arg !== '--record')
	// fast: every mutant, the tsc suites left out
	const fast = stryker({ config: 'stryker.config.json', mutate: files })
	if (fast !== 0) return fast
	const fastReport = readReport({ path: REPORT })
	// full: the fast run's survivors only, at their exact locations, with every suite
	const ranges = survivorRanges({ report: fastReport })
	if (ranges.length > 0) {
		const full = stryker({ config: 'stryker.full.config.json', mutate: ranges })
		if (full !== 0) return full
	}
	const report =
		ranges.length > 0
			? withFullRun({ fast: fastReport, full: readReport({ path: FULL_REPORT }) })
			: fastReport
	const reported = Object.keys(report.files)
	const records: SurvivorRecords = Object.fromEntries(
		reported.map((file) => [file, readRecord({ file })]),
	)
	const verdict = judgeReport({ report, records })
	const total = reported.reduce(
		(count, file) => count + (report.files[file]?.mutants.length ?? 0),
		0,
	)
	process.stdout.write(
		`${total} mutants over ${reported.length} files, ${verdict.survivors.length} surviving\n`,
	)

	if (record) {
		for (const file of reported) {
			const kept = Object.fromEntries(
				verdict.survivors
					.filter((survivor) => survivor.file === file)
					.map((survivor): [string, RecordedSurvivor] => [
						survivor.key,
						{
							line: survivor.line,
							mutation: survivor.mutation,
							equivalent: records[file]?.[survivor.key]?.equivalent ?? '',
						},
					]),
			)
			writeRecord({ file, survivors: kept })
		}
	}
	for (const survivor of verdict.unlisted)
		process.stdout.write(
			`UNLISTED ${survivor.file}:${survivor.line} ${survivor.key} ${survivor.mutation}\n`,
		)
	for (const { file, key } of record ? [] : verdict.stale)
		process.stdout.write(`STALE ${file} ${key}: listed, no longer survives\n`)
	const green = verdict.unlisted.length === 0 && (record || verdict.stale.length === 0)
	process.stdout.write(`mutation gate (ts): ${green ? 'green' : 'red'}\n`)
	return green ? 0 : 1
}

function stryker(params: { config: string; mutate: readonly string[] }): number {
	const { config, mutate } = params
	const run = spawnSync(
		'npx',
		['stryker', 'run', config, ...(mutate.length > 0 ? ['--mutate', mutate.join(',')] : [])],
		{ cwd: CREATE_ROOT, stdio: 'inherit' },
	)
	return run.status ?? 1
}

function readReport(params: { path: string }): MutationReport {
	return JSON.parse(readFileSync(params.path, 'utf-8')) as MutationReport
}

function recordPath(params: { file: string }): string {
	return join(RECORDS, `${params.file}.json`)
}

function readRecord(params: { file: string }): Record<string, RecordedSurvivor> {
	const path = recordPath(params)
	return existsSync(path)
		? (JSON.parse(readFileSync(path, 'utf-8')) as Record<string, RecordedSurvivor>)
		: {}
}

/** A file's record, written only when it lists a survivor (a file every mutant of which is killed has none). */
function writeRecord(params: { file: string; survivors: Record<string, RecordedSurvivor> }): void {
	const { file, survivors } = params
	const path = recordPath({ file })
	if (Object.keys(survivors).length === 0) {
		if (existsSync(path)) writeFileSync(path, '{}\n')
		return
	}
	mkdirSync(dirname(path), { recursive: true })
	writeFileSync(path, `${JSON.stringify(survivors, null, '\t')}\n`)
}

process.exit(main())
