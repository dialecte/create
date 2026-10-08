import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
	attributesDeclaredUnder,
	declaredUnder,
	elementChildren,
	findDeclaredEdges,
} from './declared-edges.ts'

import type { DefinitionData } from './derive.types.ts'

const noAttributes = { sequence: [], details: {} }

const definition: DefinitionData = {
	Root: {
		parents: [],
		attributes: noAttributes,
		children: {
			// Text is not an element of the definition (a foreign element a wildcard admits)
			sequence: ['Text', 'Address', 'Header', 'Note'],
			details: {
				Text: {},
				Header: {},
				Address: { attributes: noAttributes, children: noAttributes },
				// attributes alone are not a declaration: core reads an edge declaration only in full
				Note: { attributes: noAttributes },
			},
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

	it('findDeclaredEdges: only an edge carrying attributes and children declares the child', () => {
		assert.deepEqual(
			findDeclaredEdges({ definition }).map(({ parent, child }) => `${parent}>${child}`),
			['Root>Address'],
		)
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

	it("attributesDeclaredUnder: a referenced declaration with the tag level's attributes -> none, the by-tag type applies", () => {
		const sameAttributes: DefinitionData = {
			...byReference,
			Item: {
				...byReference.Item,
				attributes: { sequence: ['b'], details: {} },
			} as DefinitionData[string],
		}
		assert.equal(
			attributesDeclaredUnder({ definition: sameAttributes, parent: 'Left', child: 'Item' }),
			undefined,
		)
		assert.deepEqual(findDeclaredEdges({ definition: sameAttributes }), [])
	})

	it('findDeclaredEdges: an edge referencing one declaration of the child declares it', () => {
		assert.deepEqual(
			findDeclaredEdges({ definition: byReference }).map(
				({ parent, child }) => `${parent}>${child}`,
			),
			['Left>Item'],
		)
	})
})
