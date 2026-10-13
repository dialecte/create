import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { judgeReport, survivorKey, survivorRanges, withFullRun } from './judge.ts'

import type { MutationReport, SurvivorRecords } from './mutants-ts.types.ts'

const SOURCE = "const a = 'x'\nif (a === 'x') throw new Error('boom')\n"

/** One file, two mutants: one killed, one survived (the error message emptied). */
const REPORT: MutationReport = {
	files: {
		'src/derive/sample.ts': {
			source: SOURCE,
			mutants: [
				{
					id: '1',
					mutatorName: 'EqualityOperator',
					replacement: "a !== 'x'",
					status: 'Killed',
					location: { start: { line: 2, column: 5 }, end: { line: 2, column: 14 } },
				},
				{
					id: '2',
					mutatorName: 'StringLiteral',
					replacement: '""',
					status: 'Survived',
					location: { start: { line: 2, column: 32 }, end: { line: 2, column: 38 } },
				},
			],
		},
	},
}

const KEY = survivorKey({
	file: 'src/derive/sample.ts',
	mutatorName: 'StringLiteral',
	original: "'boom'",
	replacement: '""',
})

describe('judgeReport', () => {
	it('a survivor no record lists -> unlisted', () => {
		const verdict = judgeReport({ report: REPORT, records: {} })
		assert.deepEqual(
			verdict.unlisted.map((survivor) => survivor.key),
			[KEY],
		)
		assert.deepEqual(verdict.stale, [])
	})

	it('a survivor the record lists with a reason -> neither unlisted nor stale', () => {
		const records: SurvivorRecords = {
			'src/derive/sample.ts': {
				[KEY]: {
					line: 2,
					mutation: 'StringLiteral: \'boom\' -> ""',
					equivalent: 'a message no caller reads',
				},
			},
		}
		assert.deepEqual(judgeReport({ report: REPORT, records }), {
			survivors: judgeReport({ report: REPORT, records }).survivors,
			unlisted: [],
			stale: [],
		})
	})

	it('a listed survivor the run kills now -> stale', () => {
		const records: SurvivorRecords = {
			'src/derive/sample.ts': {
				deadbeefdeadbeef: { line: 1, mutation: 'gone', equivalent: 'was equivalent' },
			},
		}
		assert.deepEqual(judgeReport({ report: REPORT, records }).stale, [
			{ file: 'src/derive/sample.ts', key: 'deadbeefdeadbeef' },
		])
	})

	it('a timed-out mutant -> killed, no survivor', () => {
		const timedOut: MutationReport = {
			files: {
				'src/derive/sample.ts': {
					source: SOURCE,
					mutants: [{ ...REPORT.files['src/derive/sample.ts']!.mutants[1]!, status: 'Timeout' }],
				},
			},
		}
		assert.deepEqual(judgeReport({ report: timedOut, records: {} }).survivors, [])
	})
})

describe('withFullRun', () => {
	const survivor = REPORT.files['src/derive/sample.ts']!.mutants[1]!

	it('a fast-run survivor the full run kills -> killed', () => {
		const full: MutationReport = {
			files: {
				'src/derive/sample.ts': {
					source: SOURCE,
					mutants: [{ ...survivor, id: '9', status: 'Killed' }],
				},
			},
		}
		const merged = withFullRun({ fast: REPORT, full })
		assert.deepEqual(
			merged.files['src/derive/sample.ts']!.mutants.map((mutant) => mutant.status),
			['Killed', 'Killed'],
		)
	})

	it('a fast-run survivor the full run lets survive too -> survived', () => {
		const full: MutationReport = {
			files: { 'src/derive/sample.ts': { source: SOURCE, mutants: [{ ...survivor, id: '9' }] } },
		}
		assert.deepEqual(withFullRun({ fast: REPORT, full }), REPORT)
	})

	it('the ranges a full run re-mutates -> each survivor at its exact location, once each', () => {
		const twice: MutationReport = {
			files: {
				'src/derive/sample.ts': {
					source: SOURCE,
					mutants: [
						...REPORT.files['src/derive/sample.ts']!.mutants,
						{ ...survivor, id: '3', replacement: "'x'" },
					],
				},
			},
		}
		// the report counts columns from 1, a --mutate range from 0
		assert.deepEqual(survivorRanges({ report: twice }), ['src/derive/sample.ts:2:31-2:38'])
	})
})
