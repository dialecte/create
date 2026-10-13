import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { deriveRoot } from './derive-root.ts'

import type { DefinitionData, ElementData } from './derive.types.ts'

function element(parents: string[] = [], global?: true): ElementData {
	return {
		parents,
		attributes: { sequence: [], details: {} },
		children: { sequence: [], details: {} },
		...(global ? { global } : {}),
	}
}

type RootCase = { definition: DefinitionData; chosen?: string } & (
	| { expected: string }
	| { refused: RegExp }
)

const cases: Record<string, RootCase> = {
	'one element no other names -> the root': {
		definition: { Root: element(), Child: element(['Root']) },
		expected: 'Root',
	},
	'an element that only holds itself -> still a root (a recursive root)': {
		definition: { Folder: element(['Folder']) },
		expected: 'Folder',
	},
	'two candidates and one chosen -> the chosen one': {
		definition: { Invoice: element(), Order: element() },
		chosen: 'Order',
		expected: 'Order',
	},
	'two candidates and none chosen -> refused, both named in sorted order': {
		definition: { Order: element(), Invoice: element() },
		refused: /choose one.*Invoice, Order/,
	},
	'a chosen local element another one holds -> refused, the candidates named': {
		definition: { Root: element(), Child: element(['Root']) },
		chosen: 'Child',
		refused: /'Child' is not a root candidate.*Root/,
	},
	'every element held by another, none chosen -> refused, the global elements named': {
		definition: {
			First: element(['Second'], true),
			Second: element(['First'], true),
			Local: element(['First']),
		},
		refused: /choose one with --root among the global elements: First, Second$/,
	},
	'a chosen local element beside two candidates -> refused, both candidates named in order': {
		definition: { Order: element(), Invoice: element(), Line: element(['Order']) },
		chosen: 'Line',
		refused: /the candidates are: Invoice, Order$/,
	},
	'every element held by another, globals listed out of order -> named sorted': {
		definition: { Zeta: element(['Alpha'], true), Alpha: element(['Zeta'], true) },
		refused: /global elements: Alpha, Zeta$/,
	},
	'every element held by another, a global one chosen -> the chosen one (any global element may start a document)':
		{
			definition: { First: element(['Second'], true), Second: element(['First'], true) },
			chosen: 'Second',
			expected: 'Second',
		},
	'a global element another one holds, chosen beside a candidate -> the chosen one': {
		definition: { Root: element(), Child: element(['Root'], true) },
		chosen: 'Child',
		expected: 'Child',
	},
}

describe('deriveRoot', () => {
	for (const [name, testCase] of Object.entries(cases)) {
		it(name, () => {
			const { definition, chosen } = testCase
			if ('expected' in testCase)
				assert.equal(deriveRoot({ definition, chosen }), testCase.expected)
			else assert.throws(() => deriveRoot({ definition, chosen }), testCase.refused)
		})
	}
})
