import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { enumerated, typedAttributes } from './typed-attributes.ts'

import type { DataTypeData, ElementData } from './derive.types.ts'

const nothing = { sequence: [], details: {} }
/** A `version` attribute fixed to `fixed`. */
function versioned(fixed: string): ElementData['attributes'] {
	return { sequence: ['version'], details: { version: { fixed } } }
}

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

	it('a tag level whose attribute is typed, declarations enumerating it -> its own type, not hints', () => {
		/** A `mode` attribute enumerating `values`. */
		function enumerating(values: string[]): ElementData['attributes'] {
			return {
				sequence: ['mode'],
				details: { mode: { type: { builtin: 'token', facets: { enumeration: values } } } },
			}
		}
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
