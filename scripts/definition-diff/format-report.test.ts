import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { formatReport } from './format-report.ts'

import type { Difference } from './diff-definitions.types.ts'

function at(overrides: Partial<Difference>): Difference {
	return {
		element: 'Bay',
		path: ['children', 'sequence'],
		category: 'children',
		before: undefined,
		after: undefined,
		...overrides,
	}
}

type ReportCase = { differences: Difference[]; expectedLine: string }

const cases: Record<string, ReportCase> = {
	'one name added to a long list -> only that name': {
		differences: [at({ before: ['A', 'B', 'C'], after: ['A', 'B', 'X', 'C'] })],
		expectedLine: '- Bay.children.sequence: +["X"]',
	},
	'a name removed and one added -> both': {
		differences: [at({ before: ['A', 'B'], after: ['A', 'C'] })],
		expectedLine: '- Bay.children.sequence: +["C"] -["B"]',
	},
	'the same names in another order -> said so': {
		differences: [at({ before: ['A', 'B'], after: ['B', 'A'] })],
		expectedLine: '- Bay.children.sequence: same items, other order',
	},
	'an element that appears -> one word, not its whole definition': {
		differences: [at({ path: [], category: 'element', after: { tag: 'Bay', parents: [] } })],
		expectedLine: '- Bay: added',
	},
	'a value that appears -> absent before': {
		differences: [
			at({ path: ['textContent'], category: 'text-content', after: { fixed: 'R-SV' } }),
		],
		expectedLine: '- Bay.textContent: (absent) -> {"fixed":"R-SV"}',
	},
}

describe('formatReport', () => {
	for (const [name, { differences, expectedLine }] of Object.entries(cases)) {
		it(name, () => {
			const lines = formatReport({ differences }).split('\n')
			assert.ok(lines.includes(expectedLine), `missing line: ${expectedLine}\n${lines.join('\n')}`)
		})
	}

	it('no difference -> one line saying so', () => {
		assert.equal(formatReport({ differences: [] }), 'no difference\n')
	})
})
