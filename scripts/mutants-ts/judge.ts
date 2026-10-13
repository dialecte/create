/**
 * The verdict of the TypeScript mutation gate on a StrykerJS report, as `npm run mutants` gives it for the Python
 * generator: every mutant a test notices (killed, or timed out), or recorded with the reason it cannot change any
 * output. A survivor's key hashes what it changed - file, mutator, original code, replacement - so a line moving does
 * not unlist it.
 */
import { createHash } from 'node:crypto'

import type {
	MutationReport,
	ReportedMutant,
	Survivor,
	SurvivorRecords,
	Verdict,
} from './mutants-ts.types.ts'

/** Statuses that are no kill: the mutant ran and no test failed, or no test ran it. */
const SURVIVING = new Set(['Survived', 'NoCoverage'])

export function judgeReport(params: { report: MutationReport; records: SurvivorRecords }): Verdict {
	const { report, records } = params
	const survivors = Object.entries(report.files).flatMap(([file, { source, mutants }]) =>
		survivorsOf({ file, source, mutants }),
	)
	const unlisted = survivors.filter(
		(survivor) => !(records[survivor.file]?.[survivor.key]?.equivalent ?? '').trim(),
	)
	const surviving = new Set(survivors.map((survivor) => `${survivor.file}\0${survivor.key}`))
	const stale = Object.keys(report.files).flatMap((file) =>
		Object.keys(records[file] ?? {})
			.filter((key) => !surviving.has(`${file}\0${key}`))
			.map((key) => ({ file, key })),
	)
	return { survivors, unlisted, stale }
}

export function survivorKey(params: {
	file: string
	mutatorName: string
	original: string
	replacement: string
}): string {
	const { file, mutatorName, original, replacement } = params
	return createHash('sha256')
		.update([file, mutatorName, original, replacement].join('\0'))
		.digest('hex')
		.slice(0, 16)
}

function survivorsOf(params: {
	file: string
	source: string
	mutants: readonly ReportedMutant[]
}): Survivor[] {
	const { file, source, mutants } = params
	const lines = source.split('\n')
	const seen = new Map<string, number>()
	return mutants
		.filter((mutant) => SURVIVING.has(mutant.status))
		.map((mutant) => {
			const original = slice({ lines, mutant })
			const replacement = mutant.replacement ?? ''
			const base = survivorKey({ file, mutatorName: mutant.mutatorName, original, replacement })
			// the same change written twice in a file: numbered in reading order
			const count = seen.get(base) ?? 0
			seen.set(base, count + 1)
			const key = count === 0 ? base : `${base}-${count}`
			const mutation = `${mutant.mutatorName}: ${original} -> ${replacement}`.slice(0, 160)
			return { file, key, line: mutant.location.start.line, mutation }
		})
}

/** The source text a mutant replaces. */
function slice(params: { lines: readonly string[]; mutant: ReportedMutant }): string {
	const { lines, mutant } = params
	const { start, end } = mutant.location
	if (start.line === end.line)
		return (lines[start.line - 1] ?? '').slice(start.column - 1, end.column - 1)
	return [
		(lines[start.line - 1] ?? '').slice(start.column - 1),
		...lines.slice(start.line, end.line - 1),
		(lines[end.line - 1] ?? '').slice(0, end.column - 1),
	].join('\n')
}

/**
 * The fast run's report with the full run's verdicts on its survivors: a mutant either run kills is killed. The full
 * run re-mutates only the fast run's survivors, at their exact locations (`survivorRanges`).
 */
export function withFullRun(params: {
	fast: MutationReport
	full: MutationReport
}): MutationReport {
	const { fast, full } = params
	const killedInFull = new Set(
		Object.entries(full.files).flatMap(([file, { mutants }]) =>
			mutants
				.filter((mutant) => !SURVIVING.has(mutant.status))
				.map((mutant) => sameMutant({ file, mutant })),
		),
	)
	return {
		files: Object.fromEntries(
			Object.entries(fast.files).map(([file, reported]) => [
				file,
				{
					...reported,
					mutants: reported.mutants.map((mutant) =>
						SURVIVING.has(mutant.status) && killedInFull.has(sameMutant({ file, mutant }))
							? { ...mutant, status: 'Killed' }
							: mutant,
					),
				},
			]),
		),
	}
}

/**
 * Each survivor's location, once each, in StrykerJS's `--mutate file:line:column-line:column` form - its start column
 * counted from 0, where the report counts from 1 - so a full run re-mutates exactly the survivors.
 */
export function survivorRanges(params: { report: MutationReport }): string[] {
	const { report } = params
	const ranges = Object.entries(report.files).flatMap(([file, { mutants }]) =>
		mutants
			.filter((mutant) => SURVIVING.has(mutant.status))
			.map(
				({ location: { start, end } }) =>
					`${file}:${start.line}:${start.column - 1}-${end.line}:${end.column}`,
			),
	)
	return [...new Set(ranges)]
}

/** A mutant across two runs: its file, location, mutator and replacement (ids differ from run to run). */
function sameMutant(params: { file: string; mutant: ReportedMutant }): string {
	const { file, mutant } = params
	const { start, end } = mutant.location
	return [
		file,
		start.line,
		start.column,
		end.line,
		end.column,
		mutant.mutatorName,
		mutant.replacement ?? '',
	].join('\0')
}
