import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { exampleFacts } from './example-facts.ts'

import type { DataTypeData, DefinitionData, ElementData, ExampleFacts } from './derive.types.ts'

const target = { prefix: '', uri: 'urn:t' }
const other = { prefix: 'o', uri: 'urn:o' }
const nothing = { sequence: [], details: {} }

function element(params: Partial<ElementData> = {}): ElementData {
	return { namespace: target, parents: [], attributes: nothing, children: nothing, ...params }
}

const definition: DefinitionData = {
	Root: element({
		children: { sequence: ['Foreign', 'Child'], details: {} },
		contentModel: {
			kind: 'sequence',
			particles: [
				{ kind: 'element', name: 'Foreign' },
				{ kind: 'element', name: 'Child' },
			],
		},
	}),
	Child: element({
		parents: ['Root'],
		attributes: {
			sequence: [
				'optional',
				'fixed',
				'enumerated',
				'plain',
				'when',
				'count',
				'qualified',
				'o:prefixed',
			],
			details: {
				optional: {},
				fixed: { required: true, fixed: '2' },
				enumerated: {
					required: true,
					type: { builtin: 'token', facets: { enumeration: ['a', 'b'] } },
				},
				plain: { required: true },
				when: { required: true, type: { builtin: 'dateTime' } },
				count: {
					required: true,
					type: { union: [{ builtin: 'string' }, { list: { builtin: 'int' } }] },
				},
				qualified: {
					required: true,
					type: { builtin: 'QName', facets: { enumeration: ['{urn:t}x'] } },
				},
				'o:prefixed': { required: true },
			},
		},
	}),
}

describe('exampleFacts', () => {
	const facts = exampleFacts({ definition, root: 'Root' })

	it('the root -> its name and namespace', () => {
		assert.deepEqual(facts.root, { name: 'Root', namespaceUri: 'urn:t' })
	})

	it("the child -> the root's first child the definition knows", () => {
		assert.equal(facts.child?.name, 'Child')
		assert.equal(facts.child?.namespaceUri, 'urn:t')
	})

	it('each required attribute in no other namespace -> a value the schema accepts', () => {
		assert.deepEqual(facts.child?.requiredAttributes, [
			{ name: 'fixed', value: '2' },
			{ name: 'enumerated', value: 'a' },
			{ name: 'plain', value: 'hello-world' },
			// a value of its built-in type, a union's first member that has one
			{ name: 'when', value: '2000-01-01T00:00:00' },
			{ name: 'count', value: '1' },
			// a qualified name's values are not written as a document holds them
			{ name: 'qualified', value: 'hello-world' },
		])
	})

	it('a child only a type the root may take holds -> no child', () => {
		const typed = exampleFacts({
			definition: {
				...definition,
				Root: element({
					children: { sequence: ['Child'], details: {} },
					variants: ['{urn:t}tWide'],
				}),
			},
			root: 'Root',
		})
		assert.equal(typed.child, null)
	})

	it('a root holding no element of the definition -> no child', () => {
		const alone = exampleFacts({ definition: { Root: element() }, root: 'Root' })
		assert.equal(alone.child, null)
	})

	it('a child declared several ways -> the declaration the root holds, in its namespace', () => {
		const declared = exampleFacts({
			definition: {
				Root: element({
					// held in two namespaces: the first, and the declaration held in it
					children: {
						sequence: ['Child'],
						details: { Child: { declarations: { 'urn:o': ['2'], 'urn:t': ['1'] } } },
					},
					contentModel: { kind: 'element', name: 'Child' },
				}),
				Child: element({
					parents: ['Root'],
					declarations: {
						'1': {
							namespace: target,
							attributes: { sequence: ['a'], details: { a: { required: true } } },
							children: nothing,
						},
						'2': {
							namespace: other,
							attributes: { sequence: ['b'], details: { b: { required: true } } },
							children: nothing,
						},
					},
				}),
			},
			root: 'Root',
		})
		assert.deepEqual(declared.child, {
			name: 'Child',
			namespaceUri: 'urn:o',
			requiredAttributes: [{ name: 'b', value: 'hello-world' }],
		})
	})
})

describe('exampleFacts - values and shapes', () => {
	/** The facts of a root holding one child that requires attribute `a` of `type`. */
	function requiring(type: DataTypeData | undefined): ExampleFacts {
		return exampleFacts({
			definition: {
				Root: element({
					children: { sequence: ['Child'], details: {} },
					contentModel: { kind: 'element', name: 'Child' },
				}),
				Child: element({
					parents: ['Root'],
					attributes: {
						sequence: ['a'],
						details: { a: { required: true, ...(type ? { type } : {}) } },
					},
				}),
			},
			root: 'Root',
		})
	}

	// a value each built-in type accepts (python/tests/test_example_samples.py checks each against libxml2)
	const SAMPLES: Record<string, string> = {
		boolean: 'true',
		decimal: '1',
		float: '1',
		double: '1',
		integer: '1',
		long: '1',
		int: '1',
		short: '1',
		byte: '1',
		nonNegativeInteger: '1',
		positiveInteger: '1',
		unsignedLong: '1',
		unsignedInt: '1',
		unsignedShort: '1',
		unsignedByte: '1',
		nonPositiveInteger: '0',
		negativeInteger: '-1',
		dateTime: '2000-01-01T00:00:00',
		date: '2000-01-01',
		time: '00:00:00',
		duration: 'P1D',
		gYear: '2000',
		gYearMonth: '2000-01',
		gMonth: '--01',
		gMonthDay: '--01-01',
		gDay: '---01',
		anyURI: 'urn:example',
		hexBinary: '00',
		base64Binary: 'AA==',
		language: 'en',
	}
	for (const [builtin, sample] of Object.entries(SAMPLES)) {
		it(`a required ${builtin} -> ${sample}`, () => {
			assert.deepEqual(requiring({ builtin }).child?.requiredAttributes, [
				{ name: 'a', value: sample },
			])
		})
	}

	it('a union none of whose members has a sample -> the placeholder', () => {
		const facts = requiring({ union: [{ builtin: 'string' }, { builtin: 'token' }] })
		assert.deepEqual(facts.child?.requiredAttributes, [{ name: 'a', value: 'hello-world' }])
	})

	it('a root and a child in no namespace -> an empty namespace each', () => {
		const facts = exampleFacts({
			definition: {
				Root: {
					parents: [],
					attributes: nothing,
					children: { sequence: ['Child'], details: {} },
					contentModel: { kind: 'element', name: 'Child' },
				},
				Child: { parents: ['Root'], attributes: nothing, children: nothing },
			},
			root: 'Root',
		})
		assert.deepEqual(facts, {
			root: { name: 'Root', namespaceUri: '' },
			child: { name: 'Child', namespaceUri: '', requiredAttributes: [] },
		})
	})

	it('a content model opening with a wildcard, the element inside a nested group -> that element', () => {
		const facts = exampleFacts({
			definition: {
				Root: element({
					children: { sequence: ['Child'], any: true, details: {} },
					contentModel: {
						kind: 'sequence',
						particles: [
							{ kind: 'any' },
							{ kind: 'choice', particles: [{ kind: 'element', name: 'Child' }] },
						],
					},
				}),
				Child: element({ parents: ['Root'] }),
			},
			root: 'Root',
		})
		assert.equal(facts.child?.name, 'Child')
	})
})

describe('exampleFacts - its input', () => {
	it('a root the definition does not declare -> refused, named', () => {
		assert.throws(
			() => exampleFacts({ definition: {}, root: 'Missing' }),
			/'Missing' is no element of the definition/,
		)
	})
})
