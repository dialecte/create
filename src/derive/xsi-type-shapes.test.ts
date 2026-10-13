import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
	attributeShape,
	prefixedNamespaces,
	shapeKeys,
	xsiTypeLiterals,
} from './xsi-type-shapes.ts'

import type { DeclarationData, DefinitionData, ElementData, TypesData } from './derive.types.ts'

const DEFAULT = 'urn:default'
const EXT = 'urn:ext'
const XS = 'http://www.w3.org/2001/XMLSchema'

const none = { sequence: [], details: {} }
/** An element's attributes: each name required when it is written with a `!`. */
function attributes(...names: string[]): ElementData['attributes'] {
	const plain = names.map((name) => name.replace(/!$/, ''))
	return {
		sequence: plain,
		details: Object.fromEntries(
			names.map((name) => [name.replace(/!$/, ''), name.endsWith('!') ? { required: true } : {}]),
		),
	}
}
function element(content: Partial<ElementData> = {}): ElementData {
	return { parents: [], attributes: none, children: none, ...content }
}

// a root in the default namespace, an element in the other one: the namespaces the definition prefixes
const DEFINITION: DefinitionData = {
	Root: element({ namespace: { prefix: '', uri: DEFAULT } }),
	Other: element({ namespace: { prefix: 'ext', uri: EXT } }),
}
const TYPES: TypesData = {
	[`{${DEFAULT}}tWide`]: { attributes: attributes('a!', 'w'), children: none },
	[`{${EXT}}tWide`]: { attributes: attributes('a!', 'ext:x'), children: none },
	[`{${DEFAULT}}tNarrow`]: { attributes: attributes('a!'), children: none },
	[`{urn:nowhere}tLost`]: { attributes: attributes('l'), children: none },
}
const literalOf = xsiTypeLiterals({ definition: DEFINITION, root: 'Root' })
/** A variant member as `attributeShape` writes it: its literal, its type, the type's attributes. */
function variant(literal: string, clark: string) {
	return { literal, clark, attributes: TYPES[clark]?.attributes ?? none }
}

describe('prefixedNamespaces', () => {
	it('the namespaces elements, declarations and attributes carry a prefix for -> each once, by prefix', () => {
		const definition: DefinitionData = {
			Root: element({
				namespace: { prefix: '', uri: DEFAULT },
				attributes: {
					sequence: ['att:a', 'ext:b'],
					details: {
						'att:a': { namespace: { prefix: 'att', uri: 'urn:att' } },
						'ext:b': { namespace: { prefix: 'ext', uri: EXT } },
					},
				},
			}),
			Other: element({ namespace: { prefix: 'ext', uri: EXT } }),
			Twice: element({
				declarations: {
					'1': { namespace: { prefix: 'dec', uri: 'urn:dec' }, attributes: none, children: none },
				},
			}),
		}
		assert.deepEqual(prefixedNamespaces({ definition, root: 'Root' }), [
			{ prefix: 'att', uri: 'urn:att' },
			{ prefix: 'dec', uri: 'urn:dec' },
			{ prefix: 'ext', uri: EXT },
		])
	})
})

describe('prefixedNamespaces - the default namespace', () => {
	it("the root's namespace, written with a prefix by its schema -> not among them: it is the default one", () => {
		const definition: DefinitionData = {
			Root: element({ namespace: { prefix: 'ppx', uri: DEFAULT } }),
			Other: element({ namespace: { prefix: 'ext', uri: EXT } }),
		}
		assert.deepEqual(prefixedNamespaces({ definition, root: 'Root' }), [
			{ prefix: 'ext', uri: EXT },
		])
	})
})

describe('xsiTypeLiterals', () => {
	const cases: Record<string, { clark: string; expected: string | undefined }> = {
		"a type of the default namespace (the root's) -> its local name": {
			clark: `{${DEFAULT}}tWide`,
			expected: 'tWide',
		},
		'a type of a namespace the definition gives a prefix -> prefix:local': {
			clark: `{${EXT}}tWide`,
			expected: 'ext:tWide',
		},
		'a type of a namespace no element or attribute is in (a built-in) -> none: core keeps it as written':
			{
				clark: `{${XS}}anyType`,
				expected: undefined,
			},
	}
	for (const [name, { clark, expected }] of Object.entries(cases)) {
		it(name, () => assert.equal(literalOf(clark), expected))
	}

	it('a schema without a namespace -> a type in none is its local name', () => {
		const bare = xsiTypeLiterals({ definition: { Root: element() }, root: 'Root' })
		assert.equal(bare('tPlain'), 'tPlain')
	})

	it('a namespace only an attribute is in -> its prefix too', () => {
		const definition: DefinitionData = {
			Root: element({
				namespace: { prefix: '', uri: DEFAULT },
				attributes: {
					sequence: ['att:a'],
					details: { 'att:a': { namespace: { prefix: 'att', uri: 'urn:att' } } },
				},
			}),
		}
		assert.equal(xsiTypeLiterals({ definition, root: 'Root' })('{urn:att}tA'), 'att:tA')
	})
})

describe('attributeShape', () => {
	const cases: Record<
		string,
		{ content: ElementData | DeclarationData; expected: ReturnType<typeof attributeShape> }
	> = {
		'no type to name instead -> its own attributes, no literal': {
			content: element({ attributes: attributes('a!'), type: `{${DEFAULT}}tNarrow` }),
			expected: { own: { attributes: attributes('a!'), literals: [] }, variants: [] },
		},
		'a concrete type with variants -> its own member naming its type, one member per variant': {
			content: element({
				attributes: attributes('a!'),
				type: `{${DEFAULT}}tNarrow`,
				variants: [`{${DEFAULT}}tWide`, `{${EXT}}tWide`],
			}),
			expected: {
				own: { attributes: attributes('a!'), literals: ['tNarrow'] },
				variants: [variant('tWide', `{${DEFAULT}}tWide`), variant('ext:tWide', `{${EXT}}tWide`)],
			},
		},
		'an abstract type -> no own member: an instance names one of its variants': {
			content: element({
				attributes: attributes('a!'),
				type: `{${DEFAULT}}tNarrow`,
				abstractType: true,
				variants: [`{${DEFAULT}}tWide`],
			}),
			expected: { variants: [variant('tWide', `{${DEFAULT}}tWide`)] },
		},
		'a declared type core cannot store by a literal (xs:anyType) -> its own member names none': {
			content: element({ type: `{${XS}}anyType`, variants: [`{${DEFAULT}}tNarrow`] }),
			expected: {
				own: { attributes: none, literals: [] },
				variants: [variant('tNarrow', `{${DEFAULT}}tNarrow`)],
			},
		},
		'a variant core cannot store by a literal, or missing from TYPES -> left out': {
			content: element({
				variants: [`{urn:nowhere}tLost`, `{${DEFAULT}}tMissing`, `{${DEFAULT}}tWide`],
			}),
			expected: {
				own: { attributes: none, literals: [] },
				variants: [variant('tWide', `{${DEFAULT}}tWide`)],
			},
		},
		'an abstract type with no variant left -> its own attributes, as without variants': {
			content: element({
				attributes: attributes('a!'),
				abstractType: true,
				variants: [`{urn:nowhere}tLost`],
			}),
			expected: { own: { attributes: attributes('a!'), literals: [] }, variants: [] },
		},
		"a tag declared several ways -> the variants of all; its own member names each concrete declaration's type no variant types":
			{
				content: element({
					attributes: attributes('a!'),
					declarations: {
						'1': {
							attributes: attributes('a!'),
							children: none,
							type: `{${DEFAULT}}tNarrow`,
							variants: [`{${DEFAULT}}tWide`],
						},
						'2': {
							attributes: attributes('a!'),
							children: none,
							type: `{${EXT}}tWide`,
							abstractType: true,
							variants: [`{${DEFAULT}}tWide`, `{${DEFAULT}}tNarrow`],
						},
					},
				}),
				expected: {
					own: { attributes: attributes('a!'), literals: [] },
					variants: [
						variant('tWide', `{${DEFAULT}}tWide`),
						variant('tNarrow', `{${DEFAULT}}tNarrow`),
					],
				},
			},
		"a declaration's type another declaration may name instead -> typed by its own member only, not the lenient tag level":
			{
				content: element({
					attributes: attributes('a'),
					declarations: {
						'1': { attributes: attributes('a!'), children: none, type: `{${DEFAULT}}tWide` },
						'2': {
							attributes: attributes('a!'),
							children: none,
							type: `{${DEFAULT}}tNarrow`,
							variants: [`{${DEFAULT}}tWide`],
						},
					},
				}),
				expected: {
					own: { attributes: attributes('a'), literals: ['tNarrow'] },
					variants: [variant('tWide', `{${DEFAULT}}tWide`)],
				},
			},
	}
	for (const [name, { content, expected }] of Object.entries(cases)) {
		it(name, () => assert.deepEqual(attributeShape({ content, types: TYPES, literalOf }), expected))
	}
})

describe('shapeKeys', () => {
	it('no variants -> its own attributes, in order', () => {
		const shape = attributeShape({
			content: element({ attributes: attributes('b', 'a!') }),
			types: TYPES,
			literalOf,
		})
		assert.deepEqual(shapeKeys({ shape }), ['b', 'a'])
	})

	it('variants -> its own, xsi:type, then what a variant adds, each once', () => {
		const shape = attributeShape({
			content: element({
				attributes: attributes('a!'),
				variants: [`{${DEFAULT}}tWide`, `{${EXT}}tWide`],
			}),
			types: TYPES,
			literalOf,
		})
		assert.deepEqual(shapeKeys({ shape }), ['a', 'xsi:type', 'w', 'ext:x'])
	})

	it("an abstract type -> xsi:type, then its variants' attributes", () => {
		const shape = attributeShape({
			content: element({ abstractType: true, variants: [`{${DEFAULT}}tNarrow`] }),
			types: TYPES,
			literalOf,
		})
		assert.deepEqual(shapeKeys({ shape }), ['xsi:type', 'a'])
	})
})
