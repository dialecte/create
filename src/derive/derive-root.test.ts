import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { deriveRoot } from './derive-root.ts'

import type { DefinitionData, ElementData } from './derive.types.ts'

function element(parents: string[] = []): ElementData {
	return {
		parents,
		attributes: { sequence: [], details: {} },
		children: { sequence: [], details: {} },
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
	'a chosen element another one holds -> refused, the candidates named': {
		definition: { Root: element(), Child: element(['Root']) },
		chosen: 'Child',
		refused: /'Child' is not a root candidate.*Root/,
	},
	'every element held by another -> refused': {
		definition: { First: element(['Second']), Second: element(['First']) },
		refused: /No root candidate/,
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
