import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { diffDefinitions } from './diff-definitions.ts'

import type { DefinitionData, Difference } from './diff-definitions.types.ts'

type DiffCase = {
	before: DefinitionData
	after: DefinitionData
	expected: readonly Difference[]
}

function element(overrides: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		tag: 'Bay',
		namespace: { prefix: '', uri: 'urn:t' },
		parents: ['VoltageLevel'],
		attributes: { sequence: ['name'], details: { name: { required: true } } },
		children: { sequence: [], details: {} },
		...overrides,
	}
}

/** A difference of `Bay` at `path` and of what it is about; before and after are filled per case. */
function differenceAt(
	path: string[],
	category: Difference['category'],
	before: unknown,
	after: unknown,
): Difference {
	return { element: 'Bay', path, category, before, after }
}

const cases: Record<string, DiffCase> = {
	'the same definition on both sides -> no difference': {
		before: { Bay: element() },
		after: { Bay: element() },
		expected: [],
	},
	'a facet changed on an attribute -> one difference at its path, a facet one': {
		before: { Bay: element() },
		after: {
			Bay: element({
				attributes: {
					sequence: ['name'],
					details: { name: { required: true, facets: { maxLength: 32 } } },
				},
			}),
		},
		expected: [
			{
				element: 'Bay',
				path: ['attributes', 'details', 'name', 'facets'],
				category: 'facets',
				before: undefined,
				after: { maxLength: 32 },
			},
		],
	},
	'an element only one side has -> one element difference': {
		before: {},
		after: { Bay: element() },
		expected: [
			{ element: 'Bay', path: [], category: 'element', before: undefined, after: element() },
		],
	},
	'a choice member no longer required on its edge -> an occurrence difference': {
		before: {
			AccessPoint: element({
				children: { sequence: ['Server'], details: { Server: { required: true, minOccurs: 1 } } },
			}),
		},
		after: {
			AccessPoint: element({
				children: { sequence: ['Server'], details: { Server: {} } },
			}),
		},
		expected: [
			{
				element: 'AccessPoint',
				path: ['children', 'details', 'Server', 'minOccurs'],
				category: 'occurrence',
				before: 1,
				after: undefined,
			},
			{
				element: 'AccessPoint',
				path: ['children', 'details', 'Server', 'required'],
				category: 'occurrence',
				before: true,
				after: undefined,
			},
		],
	},
	'constraints declared on an edge -> a constraints difference': {
		before: {
			AccessPoint: element({ children: { sequence: ['Labels'], details: { Labels: {} } } }),
		},
		after: {
			AccessPoint: element({
				children: { sequence: ['Labels'], details: { Labels: { constraints: [{ name: 'u' }] } } },
			}),
		},
		expected: [
			{
				element: 'AccessPoint',
				path: ['children', 'details', 'Labels', 'constraints'],
				category: 'constraints',
				before: undefined,
				after: [{ name: 'u' }],
			},
		],
	},
	'an edge gaining its own text definition -> an edge-definition difference': {
		before: {
			GSEControl: element({ children: { sequence: ['Protocol'], details: { Protocol: {} } } }),
		},
		after: {
			GSEControl: element({
				children: {
					sequence: ['Protocol'],
					details: { Protocol: { textContent: { fixed: 'R-GOOSE' } } },
				},
			}),
		},
		expected: [
			{
				element: 'GSEControl',
				path: ['children', 'details', 'Protocol', 'textContent'],
				category: 'edge-definition',
				before: undefined,
				after: { fixed: 'R-GOOSE' },
			},
		],
	},
	'the synthesized xsi:type attribute gone -> an xsi-type difference': {
		before: {
			Bay: element({
				attributes: {
					sequence: ['name', 'xsi:type'],
					details: { name: { required: true }, 'xsi:type': { facets: { enumeration: ['tA'] } } },
				},
			}),
		},
		after: { Bay: element() },
		expected: [
			{
				element: 'Bay',
				path: ['attributes', 'details', 'xsi:type'],
				category: 'xsi-type',
				before: { facets: { enumeration: ['tA'] } },
				after: undefined,
			},
			{
				element: 'Bay',
				path: ['attributes', 'sequence'],
				category: 'attributes',
				before: ['name', 'xsi:type'],
				after: ['name'],
			},
		],
	},
	'the fixed text and the type of an element -> a text-content and a facets difference': {
		before: { Protocol: element({ textContent: { fixed: 'R-GOOSE' } }) },
		after: { Protocol: element({ textContent: { type: { builtin: 'normalizedString' } } }) },
		expected: [
			{
				element: 'Protocol',
				path: ['textContent', 'fixed'],
				category: 'text-content',
				before: 'R-GOOSE',
				after: undefined,
			},
			{
				element: 'Protocol',
				path: ['textContent', 'type'],
				category: 'facets',
				before: undefined,
				after: { builtin: 'normalizedString' },
			},
		],
	},
	'the same parents in another order -> no difference, parents are a set': {
		before: { Bay: element({ parents: ['VoltageLevel', 'Process'] }) },
		after: { Bay: element({ parents: ['Process', 'VoltageLevel'] }) },
		expected: [],
	},
	'a parent gained -> a parents difference': {
		before: { Bay: element() },
		after: { Bay: element({ parents: ['Process', 'VoltageLevel'] }) },
		expected: [differenceAt(['parents'], 'parents', ['VoltageLevel'], ['Process', 'VoltageLevel'])],
	},
	'the namespace of an element -> a namespace difference': {
		before: { Bay: element() },
		after: { Bay: element({ namespace: { prefix: '', uri: 'urn:other' } }) },
		expected: [differenceAt(['namespace', 'uri'], 'namespace', 'urn:t', 'urn:other')],
	},
	'the namespace on an edge -> a namespace difference': {
		before: { Bay: element({ children: { sequence: ['Text'], details: { Text: {} } } }) },
		after: {
			Bay: element({
				children: { sequence: ['Text'], details: { Text: { namespace: { uri: 'urn:x' } } } },
			}),
		},
		expected: [
			differenceAt(['children', 'details', 'Text', 'namespace'], 'namespace', undefined, {
				uri: 'urn:x',
			}),
		],
	},
	'identity fields -> an identity-fields difference': {
		before: { Bay: element() },
		after: {
			Bay: element({
				attributes: {
					sequence: ['name'],
					details: { name: { required: true } },
					identityFields: ['name'],
				},
			}),
		},
		expected: [
			differenceAt(['attributes', 'identityFields'], 'identity-fields', undefined, ['name']),
		],
	},
	'variants on an edge -> an xsi-type difference': {
		before: { Bay: element({ children: { sequence: ['P'], details: { P: {} } } }) },
		after: {
			Bay: element({
				children: { sequence: ['P'], details: { P: { variants: { '{urn:t}tP_IP': {} } } } },
			}),
		},
		expected: [
			differenceAt(['children', 'details', 'P', 'variants'], 'xsi-type', undefined, {
				'{urn:t}tP_IP': {},
			}),
		],
	},
	'a content model -> a content-model difference': {
		before: { Bay: element() },
		after: { Bay: element({ contentModel: { kind: 'sequence', particles: [] } }) },
		expected: [
			differenceAt(['contentModel'], 'content-model', undefined, {
				kind: 'sequence',
				particles: [],
			}),
		],
	},
	'documentation -> a documentation difference': {
		before: { Bay: element() },
		after: { Bay: element({ documentation: 'A bay.' }) },
		expected: [differenceAt(['documentation'], 'documentation', undefined, 'A bay.')],
	},
	'nillable -> a text-content difference': {
		before: { Bay: element() },
		after: { Bay: element({ nillable: true }) },
		expected: [differenceAt(['nillable'], 'text-content', undefined, true)],
	},
	'the same children in another order -> a children difference, their order is the order export writes':
		{
			before: { Bay: element({ children: { sequence: ['LNode', 'Function'], details: {} } }) },
			after: { Bay: element({ children: { sequence: ['Function', 'LNode'], details: {} } }) },
			expected: [
				differenceAt(
					['children', 'sequence'],
					'children',
					['LNode', 'Function'],
					['Function', 'LNode'],
				),
			],
		},
	'the tag of an element -> an element difference': {
		before: { Bay: element() },
		after: { Bay: element({ tag: 'Bay2' }) },
		expected: [differenceAt(['tag'], 'element', 'Bay', 'Bay2')],
	},
	'the same particles written with their keys in another order -> no difference': {
		before: {
			Bay: element({
				contentModel: { kind: 'sequence', particles: [{ kind: 'element', name: 'A', min: 0 }] },
			}),
		},
		after: {
			Bay: element({
				contentModel: { particles: [{ min: 0, name: 'A', kind: 'element' }], kind: 'sequence' },
			}),
		},
		expected: [],
	},
}

describe('diffDefinitions', () => {
	for (const [name, testCase] of Object.entries(cases)) {
		it(name, () => {
			const { before, after, expected } = testCase
			assert.deepEqual(diffDefinitions({ before, after }), expected)
		})
	}
})
