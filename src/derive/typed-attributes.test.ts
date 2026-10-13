import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { attributesDeclaredUnder } from './declared-edges.ts'
import { enumerated, typedAttributes } from './typed-attributes.ts'

import type { DataTypeData, DefinitionData, ElementData } from './derive.types.ts'

const nothing = { sequence: [], details: {} }
const versioned = (fixed: string) => ({ sequence: ['version'], details: { version: { fixed } } })

describe('typedAttributes', () => {
	it('a tag level with a value of its own (its declarations agree) -> that value, not hints', () => {
		const tag: ElementData = {
			parents: [],
			attributes: versioned('2'),
			children: nothing,
			declarations: {
				'1': { attributes: versioned('2'), children: nothing },
				'2': { attributes: versioned('2'), children: nothing },
			},
		}
		assert.deepEqual(typedAttributes(tag).details.version, { fixed: '2' })
	})

	it('a declaration admitting no type, beside one that does -> its own type, without xsi:type', () => {
		// Item under Left admits a type, under Right none: same attributes, other types offered
		const definition: DefinitionData = {
			Left: {
				parents: [],
				attributes: nothing,
				children: { sequence: ['Item'], details: { Item: { declarations: { 'urn:t': ['1'] } } } },
			},
			Right: {
				parents: [],
				attributes: nothing,
				children: { sequence: ['Item'], details: { Item: { declarations: { 'urn:t': ['2'] } } } },
			},
			Item: {
				parents: ['Left', 'Right'],
				attributes: { sequence: ['a'], details: { a: {} } },
				children: nothing,
				declarations: {
					'1': {
						attributes: { sequence: ['a'], details: { a: {} } },
						children: nothing,
						variants: ['{urn:t}tWide'],
					},
					'2': { attributes: { sequence: ['a'], details: { a: {} } }, children: nothing },
				},
			},
		}
		assert.deepEqual(
			attributesDeclaredUnder({ definition, parent: 'Right', child: 'Item' })?.sequence,
			['a'],
		)
		assert.equal(attributesDeclaredUnder({ definition, parent: 'Left', child: 'Item' }), undefined)
	})

	it('a tag level whose attribute is typed, declarations enumerating it -> its own type, not hints', () => {
		const enumerating = (values: string[]) => ({
			sequence: ['mode'],
			details: { mode: { type: { builtin: 'token', facets: { enumeration: values } } } },
		})
		const tag: ElementData = {
			parents: [],
			attributes: { sequence: ['mode'], details: { mode: { type: { builtin: 'token' } } } },
			children: nothing,
			declarations: {
				'1': { attributes: enumerating(['a']), children: nothing },
				'2': { attributes: enumerating(['b']), children: nothing },
			},
		}
		assert.deepEqual(typedAttributes(tag).details.mode, { type: { builtin: 'token' } })
	})
})

describe('enumerated', () => {
	const cases: Record<string, { datatype: DataTypeData | undefined; expected: string[] }> = {
		'no datatype -> none': { datatype: undefined, expected: [] },
		'an empty enumeration -> none': {
			datatype: { builtin: 'token', facets: { enumeration: [] } },
			expected: [],
		},
		'a NOTATION enumeration -> none, its values are qualified names': {
			datatype: { builtin: 'NOTATION', facets: { enumeration: ['{urn:t}gif'] } },
			expected: [],
		},
		'a union whose members enumerate nothing -> none': {
			datatype: { union: [{ builtin: 'string' }, { builtin: 'token' }] },
			expected: [],
		},
		"a union -> its members' values, once each": {
			datatype: {
				union: [
					{ builtin: 'token', facets: { enumeration: ['a', 'b'] } },
					{ builtin: 'token', facets: { enumeration: ['b', 'c'] } },
				],
			},
			expected: ['a', 'b', 'c'],
		},
	}
	for (const [name, { datatype, expected }] of Object.entries(cases)) {
		it(name, () => assert.deepEqual(enumerated(datatype), expected))
	}
})
