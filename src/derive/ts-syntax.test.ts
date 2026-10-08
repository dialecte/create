import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { deriveTypeNames, tsKey, tsMember, tsRecord, tsString } from './ts-syntax.ts'

describe('ts-syntax', () => {
	const literals: Record<string, [string, string]> = {
		'a plain value -> single quoted': ['Bay', "'Bay'"],
		'a quote and a backslash -> escaped': ["it's\\", "'it\\'s\\\\'"],
		'a line break, a carriage return and a tab -> escaped': ['a\nb\rc\td', "'a\\nb\\rc\\td'"],
	}
	for (const [name, [value, expected]] of Object.entries(literals)) {
		it(`tsString: ${name}`, () => assert.equal(tsString(value), expected))
	}

	const keys: Record<string, [string, string, string]> = {
		'an identifier -> bare': ['Bay', 'Bay', '.Bay'],
		'a prefixed name -> quoted': [
			'eIEC61850-6-100:version',
			"'eIEC61850-6-100:version'",
			"['eIEC61850-6-100:version']",
		],
		'a name with a middle dot, an identifier for XML and for the generator -> bare': [
			'a·b',
			'a·b',
			'.a·b',
		],
		'a hyphenated name -> quoted': ['boolean-value', "'boolean-value'", "['boolean-value']"],
	}
	for (const [name, [value, key, member]] of Object.entries(keys)) {
		it(`tsKey / tsMember: ${name}`, () => {
			assert.equal(tsKey(value), key)
			assert.equal(tsMember(value), member)
		})
	}

	it('tsRecord: keys sorted, each list kept in its order', () => {
		assert.equal(
			tsRecord({ Zeta: ['b', 'a'], Alpha: [] }),
			"{\n\tAlpha: [],\n\tZeta: ['b', 'a'],\n}",
		)
	})

	it('deriveTypeNames: identifiers kept, others PascalCase, a clash numbered in sorted order', () => {
		// given unsorted: the suffix still goes to the name that sorts later
		const names = deriveTypeNames(['boolean.value', 'Bay', '1st', 'boolean-value'])
		assert.deepEqual(Object.fromEntries(names), {
			Bay: 'Bay',
			'1st': '_1st',
			'boolean-value': 'BooleanValue',
			'boolean.value': 'BooleanValue_2',
		})
	})
})
