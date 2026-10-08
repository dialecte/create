import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { deriveGraph } from './derive-graph.ts'

import type { DefinitionData, DerivedGraph, ElementData } from './derive.types.ts'

function element(params: { parents?: string[]; children?: string[] } = {}): ElementData {
	const { parents = [], children = [] } = params
	return {
		parents,
		attributes: { sequence: [], details: {} },
		children: {
			sequence: children,
			details: Object.fromEntries(children.map((child) => [child, {}])),
		},
	}
}

type GraphCase = { definition: DefinitionData; expected: DerivedGraph }

const cases: Record<string, GraphCase> = {
	'a root holding a child holding a grandchild -> the closures reach through': {
		definition: {
			Root: element({ children: ['A'] }),
			A: element({ parents: ['Root'], children: ['B'] }),
			B: element({ parents: ['A'] }),
		},
		expected: {
			children: { A: ['B'], B: [], Root: ['A'] },
			parents: { A: ['Root'], B: ['A'], Root: [] },
			descendants: { A: ['B'], B: [], Root: ['A', 'B'] },
			ancestors: { A: ['Root'], B: ['A', 'Root'], Root: [] },
		},
	},
	'children written out of alphabetical order, parents too -> children keep the definition order, the rest is sorted':
		{
			definition: {
				Root: element({ children: ['Zeta', 'Alpha'] }),
				Zeta: element({ parents: ['Root'] }),
				Alpha: element({ parents: ['Zeta', 'Root'], children: ['Omega', 'Beta'] }),
				Omega: element({ parents: ['Alpha'] }),
				Beta: element({ parents: ['Alpha'] }),
			},
			expected: {
				children: {
					Alpha: ['Omega', 'Beta'],
					Beta: [],
					Omega: [],
					Root: ['Zeta', 'Alpha'],
					Zeta: [],
				},
				parents: {
					Alpha: ['Root', 'Zeta'],
					Beta: ['Alpha'],
					Omega: ['Alpha'],
					Root: [],
					Zeta: ['Root'],
				},
				descendants: {
					Alpha: ['Beta', 'Omega'],
					Beta: [],
					Omega: [],
					Root: ['Alpha', 'Beta', 'Omega', 'Zeta'],
					Zeta: [],
				},
				ancestors: {
					Alpha: ['Root', 'Zeta'],
					Beta: ['Alpha', 'Root', 'Zeta'],
					Omega: ['Alpha', 'Root', 'Zeta'],
					Root: [],
					Zeta: ['Root'],
				},
			},
		},
	'an element that nests in itself -> the closures end, it is its own descendant and ancestor': {
		definition: {
			Root: element({ children: ['SDI'] }),
			SDI: element({ parents: ['Root', 'SDI'], children: ['SDI'] }),
		},
		expected: {
			children: { Root: ['SDI'], SDI: ['SDI'] },
			parents: { Root: [], SDI: ['Root', 'SDI'] },
			descendants: { Root: ['SDI'], SDI: ['SDI'] },
			ancestors: { Root: [], SDI: ['Root', 'SDI'] },
		},
	},
}

describe('deriveGraph', () => {
	for (const [name, testCase] of Object.entries(cases)) {
		it(name, () => {
			assert.deepEqual(deriveGraph({ definition: testCase.definition }), testCase.expected)
		})
	}
})
