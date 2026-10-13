import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
	declaredUnder,
	elementChildren,
	findDeclaredEdges,
	shapeDeclaredUnder,
} from './declared-edges.ts'
import { xsiTypeLiterals } from './xsi-type-shapes.ts'

import type { DefinitionData, LiteralOf, TypesData } from './derive.types.ts'

const noAttributes = { sequence: [], details: {} }
/** No type to name with xsi:type: the edges differ by their attributes alone. */
const NO_TYPES: { types: TypesData; literalOf: LiteralOf } = {
	types: {},
	literalOf: () => undefined,
}

const definition: DefinitionData = {
	Root: {
		parents: [],
		attributes: noAttributes,
		children: {
			// Text is not an element of the definition (a foreign element a wildcard admits)
			sequence: ['Text', 'Address', 'Header', 'Note'],
			details: {},
		},
	},
	Address: { parents: ['Root'], attributes: noAttributes, children: noAttributes },
	Header: { parents: ['Root'], attributes: noAttributes, children: noAttributes },
	Note: { parents: ['Root'], attributes: noAttributes, children: noAttributes },
}

// a child declared several ways, its parents naming the declaration they hold
const byReference: DefinitionData = {
	Root: {
		parents: [],
		attributes: noAttributes,
		children: {
			sequence: ['Left', 'Item'],
			// Item in two namespaces under Root: no one declaration to name
			details: { Item: { declarations: { 'urn:a': ['1'], 'urn:b': ['2'] } } },
		},
	},
	Left: {
		parents: ['Root'],
		attributes: noAttributes,
		children: { sequence: ['Item'], details: { Item: { declarations: { 'urn:b': ['2'] } } } },
	},
	Item: {
		parents: ['Left', 'Root'],
		attributes: { sequence: ['a', 'b'], details: {} },
		children: noAttributes,
		declarations: {
			'1': { attributes: { sequence: ['a'], details: {} }, children: noAttributes },
			'2': { attributes: { sequence: ['b'], details: {} }, children: noAttributes },
		},
	},
}

describe('declared-edges', () => {
	it('elementChildren: the children that are elements of the definition, in its order', () => {
		assert.deepEqual(elementChildren({ definition, parent: 'Root' }), ['Address', 'Header', 'Note'])
	})

	it('findDeclaredEdges: a child declared one way -> no edge of its own', () => {
		assert.deepEqual(findDeclaredEdges({ definition, ...NO_TYPES }), [])
	})

	it('declaredUnder: a reference to one declaration of the child -> that declaration', () => {
		assert.deepEqual(
			declaredUnder({ definition: byReference, parent: 'Left', child: 'Item' })?.attributes
				.sequence,
			['b'],
		)
	})

	it('declaredUnder: one namespace decided beside another the particles leave open -> none, the tag level applies', () => {
		const mixed: DefinitionData = {
			...byReference,
			Left: {
				...byReference.Left,
				children: {
					sequence: ['Item'],
					details: { Item: { declarations: { 'urn:a': ['1'], 'urn:b': ['2', '3'] } } },
				},
			} as DefinitionData[string],
		}
		assert.equal(declaredUnder({ definition: mixed, parent: 'Left', child: 'Item' }), undefined)
	})

	it('declaredUnder: one namespace whose particles hold two declarations -> none, the particle decides', () => {
		const positional: DefinitionData = {
			...byReference,
			Left: {
				...byReference.Left,
				children: {
					sequence: ['Item'],
					details: { Item: { declarations: { 'urn:b': ['1', '2'] } } },
				},
			} as DefinitionData[string],
		}
		assert.equal(
			declaredUnder({ definition: positional, parent: 'Left', child: 'Item' }),
			undefined,
		)
	})

	it('declaredUnder: references to several declarations (one per namespace) -> none, the tag level applies', () => {
		assert.equal(
			declaredUnder({ definition: byReference, parent: 'Root', child: 'Item' }),
			undefined,
		)
	})

	it("shapeDeclaredUnder: a referenced declaration with the tag level's attributes -> none, the by-tag type applies", () => {
		const sameAttributes: DefinitionData = {
			...byReference,
			Item: {
				...byReference.Item,
				attributes: { sequence: ['b'], details: {} },
			} as DefinitionData[string],
		}
		assert.equal(
			shapeDeclaredUnder({
				definition: sameAttributes,
				...NO_TYPES,
				parent: 'Left',
				child: 'Item',
			}),
			undefined,
		)
		assert.deepEqual(findDeclaredEdges({ definition: sameAttributes, ...NO_TYPES }), [])
	})

	it("shapeDeclaredUnder: a referenced declaration with the tag level's attributes in another key order -> none, the same data", () => {
		const reordered: DefinitionData = {
			...byReference,
			Item: {
				...byReference.Item,
				attributes: {
					sequence: ['b'],
					details: {
						b: { required: true, type: { builtin: 'token', facets: { enumeration: ['x'] } } },
					},
				},
				declarations: {
					'1': { attributes: { sequence: ['a'], details: {} }, children: noAttributes },
					'2': {
						attributes: {
							details: {
								b: { type: { facets: { enumeration: ['x'] }, builtin: 'token' }, required: true },
							},
							sequence: ['b'],
						},
						children: noAttributes,
					},
				},
			} as DefinitionData[string],
		}
		assert.equal(
			shapeDeclaredUnder({ definition: reordered, ...NO_TYPES, parent: 'Left', child: 'Item' }),
			undefined,
		)
	})

	it('shapeDeclaredUnder: a referenced declaration differing only by its identity fields -> none, its type is the same', () => {
		const identified: DefinitionData = {
			...byReference,
			Item: {
				...byReference.Item,
				attributes: { sequence: ['b'], details: {} },
				declarations: {
					'1': { attributes: { sequence: ['a'], details: {} }, children: noAttributes },
					'2': {
						attributes: { sequence: ['b'], details: {}, identityFields: ['b'] },
						children: noAttributes,
					},
				},
			} as DefinitionData[string],
		}
		assert.equal(
			shapeDeclaredUnder({ definition: identified, ...NO_TYPES, parent: 'Left', child: 'Item' }),
			undefined,
		)
	})

	it('findDeclaredEdges: an edge referencing one declaration of the child declares it', () => {
		assert.deepEqual(
			findDeclaredEdges({ definition: byReference, ...NO_TYPES }).map(
				({ parent, child }) => `${parent}>${child}`,
			),
			['Left>Item'],
		)
	})

	it('shapeDeclaredUnder: the same attributes, other types to name -> a type of its own where they differ', () => {
		// Item under Left may name tWide, under Right no type: the tag level offers tWide
		const item = { sequence: ['a'], details: { a: {} } }
		const variants: DefinitionData = {
			Left: {
				namespace: { prefix: '', uri: 'urn:t' },
				parents: [],
				attributes: noAttributes,
				children: { sequence: ['Item'], details: { Item: { declarations: { 'urn:t': ['1'] } } } },
			},
			Right: {
				parents: [],
				attributes: noAttributes,
				children: { sequence: ['Item'], details: { Item: { declarations: { 'urn:t': ['2'] } } } },
			},
			Item: {
				parents: ['Left', 'Right'],
				attributes: item,
				children: noAttributes,
				variants: ['{urn:t}tWide'],
				declarations: {
					'1': { attributes: item, children: noAttributes, variants: ['{urn:t}tWide'] },
					'2': { attributes: item, children: noAttributes },
				},
			},
		}
		const context = {
			definition: variants,
			types: { '{urn:t}tWide': { attributes: item, children: noAttributes } },
			literalOf: xsiTypeLiterals({ definition: variants, root: 'Left' }),
		}
		assert.deepEqual(shapeDeclaredUnder({ ...context, parent: 'Right', child: 'Item' }), {
			own: { attributes: item, literals: [] },
			variants: [],
		})
		assert.equal(shapeDeclaredUnder({ ...context, parent: 'Left', child: 'Item' }), undefined)
	})
})
