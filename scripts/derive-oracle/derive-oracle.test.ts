import assert from 'node:assert/strict'
import { readdirSync } from 'node:fs'
import { describe, it } from 'node:test'

import { checkDerivation, describeDisagreements } from './derive-oracle.ts'

import type { DefinitionData, ElementData } from '../../src/derive/derive.types.ts'
import type { Disagreement, EmittedConstants } from './derive-oracle.types.ts'

function element(
	params: Omit<Partial<ElementData>, 'children'> & { children?: string[] } = {},
): ElementData {
	const { children = [], ...rest } = params
	return {
		parents: [],
		attributes: { sequence: [], details: {} },
		children: { sequence: children, details: {} },
		...rest,
	}
}

/** An element holding `child` in the declaration of it numbered `declaration`. */
function holding(params: { parents: string[]; child: string; declaration: string }): ElementData {
	const { parents, child, declaration } = params
	return {
		...element({ parents }),
		children: {
			sequence: [child],
			details: { [child]: { declarations: { 'urn:t': [declaration] } } },
		},
	}
}

/** Root holds A, A holds B; A requires `a`. */
const DEFINITION: DefinitionData = {
	Root: element({ children: ['A'] }),
	A: element({
		parents: ['Root'],
		children: ['B'],
		attributes: { sequence: ['a', 'b'], details: { a: { required: true }, b: {} } },
	}),
	B: element({ parents: ['A'] }),
}

/** The constants the generator writes for DEFINITION, written by hand. */
const CONSTANTS: EmittedConstants = {
	ELEMENT_NAMES: ['A', 'B', 'Root'],
	CHILDREN: { A: ['B'], B: [], Root: ['A'] },
	PARENTS: { A: ['Root'], B: ['A'], Root: [] },
	DESCENDANTS: { A: ['B'], B: [], Root: ['A', 'B'] },
	ANCESTORS: { A: ['Root'], B: ['A', 'Root'], Root: [] },
	ROOT_ELEMENT: 'Root',
	ATTRIBUTES: {
		byTag: { A: { a: '', b: '' }, B: {}, Root: {} },
		byParent: { A: { B: {} }, Root: { A: { a: '', b: '' } } },
	},
	REQUIRED_ATTRIBUTES: { A: ['a'], B: [], Root: [] },
}

type OracleCase = {
	definition?: DefinitionData
	constants: EmittedConstants
	expected: Disagreement[]
}

const cases: Record<string, OracleCase> = {
	'constants the definition implies -> no disagreement': { constants: CONSTANTS, expected: [] },
	'a child missing from CHILDREN -> a children disagreement': {
		constants: { ...CONSTANTS, CHILDREN: { ...CONSTANTS.CHILDREN, Root: [] } },
		expected: [{ fact: 'children', element: 'Root', expected: ['A'], emitted: [] }],
	},
	'a parent missing from PARENTS -> a parents disagreement': {
		constants: { ...CONSTANTS, PARENTS: { ...CONSTANTS.PARENTS, B: [] } },
		expected: [{ fact: 'parents', element: 'B', expected: ['A'], emitted: [] }],
	},
	'parents the definition lists but no element holds -> read from what holds the element': {
		definition: { ...DEFINITION, B: element({ parents: ['Root'] }) },
		constants: { ...CONSTANTS, PARENTS: { ...CONSTANTS.PARENTS, B: ['Root'] } },
		expected: [{ fact: 'parents', element: 'B', expected: ['A'], emitted: ['Root'] }],
	},
	'a grandchild missing from DESCENDANTS -> a descendants disagreement': {
		constants: { ...CONSTANTS, DESCENDANTS: { ...CONSTANTS.DESCENDANTS, Root: ['A'] } },
		expected: [{ fact: 'descendants', element: 'Root', expected: ['A', 'B'], emitted: ['A'] }],
	},
	'a grandparent missing from ANCESTORS -> an ancestors disagreement': {
		constants: { ...CONSTANTS, ANCESTORS: { ...CONSTANTS.ANCESTORS, B: ['A'] } },
		expected: [{ fact: 'ancestors', element: 'B', expected: ['A', 'Root'], emitted: ['A'] }],
	},
	'an element nesting in itself -> its own descendant and ancestor': {
		definition: { Root: element({ children: ['Root'] }) },
		constants: {
			...CONSTANTS,
			ELEMENT_NAMES: ['Root'],
			CHILDREN: { Root: ['Root'] },
			PARENTS: { Root: ['Root'] },
			DESCENDANTS: { Root: [] },
			ANCESTORS: { Root: [] },
			ATTRIBUTES: { byTag: { Root: {} }, byParent: { Root: { Root: {} } } },
			REQUIRED_ATTRIBUTES: { Root: [] },
		},
		expected: [
			{ fact: 'descendants', element: 'Root', expected: ['Root'], emitted: [] },
			{ fact: 'ancestors', element: 'Root', expected: ['Root'], emitted: [] },
		],
	},
	'an element missing from ELEMENT_NAMES -> an elements disagreement': {
		constants: { ...CONSTANTS, ELEMENT_NAMES: ['A', 'Root'] },
		expected: [
			{ fact: 'elements', element: '*', expected: ['A', 'B', 'Root'], emitted: ['A', 'Root'] },
		],
	},
	'a root another element holds -> a root disagreement naming the candidates': {
		constants: { ...CONSTANTS, ROOT_ELEMENT: 'A' },
		expected: [{ fact: 'root', element: 'A', expected: ['Root'], emitted: 'A' }],
	},
	'a global root another element holds -> no disagreement (any global element may start a document)':
		{
			definition: { ...DEFINITION, A: { ...DEFINITION.A!, global: true } },
			constants: { ...CONSTANTS, ROOT_ELEMENT: 'A' },
			expected: [],
		},
	'an attribute missing from ATTRIBUTES.byTag -> an attributes disagreement': {
		constants: {
			...CONSTANTS,
			ATTRIBUTES: {
				...CONSTANTS.ATTRIBUTES,
				byTag: { ...CONSTANTS.ATTRIBUTES.byTag, A: { a: '' } },
			},
		},
		expected: [{ fact: 'attributes', element: 'A', expected: ['a', 'b'], emitted: ['a'] }],
	},
	'an element with xsi:type variants -> xsi:type among its attributes': {
		definition: { ...DEFINITION, B: element({ parents: ['A'], variants: ['{urn:t}tB'] }) },
		constants: CONSTANTS,
		expected: [
			{ fact: 'attributes', element: 'B', expected: ['xsi:type'], emitted: [] },
			{
				fact: 'attributes-by-parent',
				element: 'B',
				parent: 'A',
				expected: ['xsi:type'],
				emitted: [],
			},
		],
	},
	'a required attribute missing from REQUIRED_ATTRIBUTES -> a required disagreement': {
		constants: { ...CONSTANTS, REQUIRED_ATTRIBUTES: { ...CONSTANTS.REQUIRED_ATTRIBUTES, A: [] } },
		expected: [{ fact: 'required', element: 'A', expected: ['a'], emitted: [] }],
	},
	'a child missing under its parent in ATTRIBUTES.byParent -> an attributes-by-parent disagreement':
		{
			constants: {
				...CONSTANTS,
				ATTRIBUTES: {
					...CONSTANTS.ATTRIBUTES,
					byParent: { ...CONSTANTS.ATTRIBUTES.byParent, A: {} },
				},
			},
			expected: [
				{
					fact: 'attributes-by-parent',
					element: 'B',
					parent: 'A',
					expected: [],
					emitted: undefined,
				},
			],
		},
	'a tag declared one way under each parent -> each parent offers its declaration attributes': {
		definition: {
			Root: element({ children: ['Left', 'Right'] }),
			Left: holding({ parents: ['Root'], child: 'P', declaration: '1' }),
			Right: holding({ parents: ['Root'], child: 'P', declaration: '2' }),
			P: element({
				parents: ['Left', 'Right'],
				attributes: { sequence: ['x', 'y'], details: { x: {}, y: {} } },
				declarations: {
					'1': {
						attributes: { sequence: ['x'], details: { x: {} } },
						children: { sequence: [], details: {} },
					},
					'2': {
						attributes: { sequence: ['y'], details: { y: {} } },
						children: { sequence: [], details: {} },
					},
				},
			}),
		},
		constants: {
			ELEMENT_NAMES: ['Left', 'P', 'Right', 'Root'],
			CHILDREN: { Left: ['P'], P: [], Right: ['P'], Root: ['Left', 'Right'] },
			PARENTS: { Left: ['Root'], P: ['Left', 'Right'], Right: ['Root'], Root: [] },
			DESCENDANTS: { Left: ['P'], P: [], Right: ['P'], Root: ['Left', 'P', 'Right'] },
			ANCESTORS: { Left: ['Root'], P: ['Left', 'Right', 'Root'], Right: ['Root'], Root: [] },
			ROOT_ELEMENT: 'Root',
			ATTRIBUTES: {
				byTag: { Left: {}, P: { x: '', y: '' }, Right: {}, Root: {} },
				byParent: {
					Left: { P: { x: '' } },
					Right: { P: { x: '', y: '' } },
					Root: { Left: {}, Right: {} },
				},
			},
			REQUIRED_ATTRIBUTES: { Left: [], P: [], Right: [], Root: [] },
		},
		expected: [
			{
				fact: 'attributes-by-parent',
				element: 'P',
				parent: 'Right',
				expected: ['y'],
				emitted: ['x', 'y'],
			},
		],
	},
}

describe('checkDerivation', () => {
	for (const [name, { definition = DEFINITION, constants, expected }] of Object.entries(cases)) {
		it(name, () => {
			assert.deepEqual(checkDerivation({ definition, constants }), expected)
		})
	}
})

// the committed dialectes: their constants as the generator wrote them, against their definition
const FIXTURES = new URL('../../test/fixtures/definition/', import.meta.url)
const FIXTURE_NAMES = readdirSync(FIXTURES, { withFileTypes: true })
	.filter((entry) => entry.isDirectory())
	.map((entry) => entry.name)
	.sort()

describe('the committed dialectes agree with the oracle', () => {
	for (const fixture of FIXTURE_NAMES) {
		it(`${fixture} -> no disagreement`, async () => {
			const { DEFINITION } = await import(
				new URL(`${fixture}/definition.generated.ts`, FIXTURES).href
			)
			const constants = await import(new URL(`${fixture}/constants.generated.ts`, FIXTURES).href)
			assert.deepEqual(checkDerivation({ definition: DEFINITION, constants }), [])
		})
	}
})

describe('describeDisagreements', () => {
	it('none -> agrees', () => {
		assert.equal(describeDisagreements({ disagreements: [] }), 'agrees with the definition')
	})
	it('one under a parent -> the count, then the fact under its parent', () => {
		const disagreements: Disagreement[] = [
			{
				fact: 'attributes-by-parent',
				element: 'P',
				parent: 'Right',
				expected: ['y'],
				emitted: ['x'],
			},
		]
		assert.equal(
			describeDisagreements({ disagreements }),
			'1 disagreement(s)\n    attributes-by-parent Right > P: expected ["y"], emitted ["x"]',
		)
	})
})
