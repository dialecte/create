import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { elementChildren, findDeclaredEdges } from './declared-edges.ts'

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
})
