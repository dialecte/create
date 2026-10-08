import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { emitConstantsSource } from './emit-constants.ts'
import { emitTypesSource } from './emit-types.ts'

import type { DefinitionData, ElementData } from './derive.types.ts'

// A root holding an Address and a PhysConn, both holding a P declared differently under each: the
// tag level is the union, each parent's edge carries the declaration.
const pUnderAddress: ElementData['attributes'] = {
	sequence: ['type'],
	details: { type: { required: true, facets: { enumeration: ['IP', 'MAC'] } } },
}
const pUnderPhysConn: ElementData['attributes'] = {
	sequence: ['type'],
	details: { type: { required: true, fixed: 'Plug' } },
}
const noChildren = { sequence: [], details: {} }

// written out of order on purpose (PhysConn before Address, version before id): what the
// emitters sort must come out sorted
const definition: DefinitionData = {
	Root: {
		parents: [],
		attributes: {
			sequence: ['version', 'id'],
			details: { version: { required: true }, id: { required: true } },
		},
		children: {
			sequence: ['PhysConn', 'Address', 'Empty'],
			details: { Address: {}, PhysConn: {}, Empty: {} },
		},
		contentModel: {
			kind: 'sequence',
			minOccurs: 1,
			maxOccurs: 1,
			particles: [
				{ kind: 'element', name: 'PhysConn' },
				{ kind: 'element', name: 'Address', maxOccurs: 1 },
				{ kind: 'element', name: 'Empty', maxOccurs: 1 },
			],
		},
	},
	PhysConn: {
		parents: ['Root'],
		attributes: { sequence: [], details: {} },
		children: {
			sequence: ['P'],
			details: { P: { attributes: pUnderPhysConn, children: noChildren } },
		},
	},
	Address: {
		parents: ['Root'],
		attributes: { sequence: [], details: {} },
		children: {
			sequence: ['P'],
			details: { P: { attributes: pUnderAddress, children: noChildren } },
		},
	},
	// an element without attributes
	Empty: { parents: ['Root'], attributes: { sequence: [], details: {} }, children: noChildren },
	P: {
		parents: ['Address', 'PhysConn'],
		attributes: { sequence: ['type'], details: { type: {} } },
		children: noChildren,
	},
}

describe('emitConstantsSource', () => {
	const source = emitConstantsSource({ definition, root: 'Root' })

	const expectedLines: Record<string, string> = {
		'the root -> ROOT_ELEMENT': "export const ROOT_ELEMENT = 'Root' as const",
		'a child at most once under the root -> a singleton, a repeatable one not':
			"export const SINGLETON_ELEMENTS = ['Address', 'Empty', 'Root'] as const",
		'the types of the homonyms -> imported, sorted':
			"import type { AvailableElement, AttributesOf, AttributesByParent, AttributesPInAddress, AttributesPInPhysConn } from './types.generated'",
		'an element without attributes -> an empty skeleton typed by its element':
			"\tEmpty: {} as AttributesOf<'Empty'>,",
		'a homonym -> its own skeleton under each parent':
			"\t\t\tP: { type: '' as string } as AttributesPInAddress,",
		'an element declared once -> the by-tag object under its parent':
			'\t\t\tAddress: ATTRIBUTES_BY_TAG.Address,',
		'required attributes -> listed for their element, sorted': "\tRoot: ['id', 'version'],",
	}
	for (const [name, line] of Object.entries(expectedLines)) {
		it(name, () => assert.ok(source.split('\n').includes(line), `missing line: ${line}`))
	}
})

describe('emitTypesSource', () => {
	const source = emitTypesSource({ definition })

	const expectedBlocks: Record<string, string> = {
		'an attribute declared once -> optional string at the tag level':
			'export type AttributesP = {\n\ttype?: string\n}',
		'an enumeration under a parent -> the union of its values, open to others':
			"export type AttributesPInAddress = {\n\ttype: 'IP' | 'MAC' | (string & {})\n}",
		'a fixed value under a parent -> its literal':
			"export type AttributesPInPhysConn = {\n\ttype: 'Plug'\n}",
		'a homonym in the parent map -> the type of its declaration there':
			'\tPhysConn: {\n\t\tP: AttributesPInPhysConn\n\t}',
	}
	for (const [name, block] of Object.entries(expectedBlocks)) {
		it(name, () => assert.ok(source.includes(block), `missing block:\n${block}`))
	}

	it('the declarations of a homonym -> one type each, in the order of their parents', () => {
		assert.ok(
			source.indexOf('AttributesPInAddress = {') < source.indexOf('AttributesPInPhysConn = {'),
		)
	})

	it('the names of the required and optional attributes -> derived from the constants', () => {
		assert.ok(source.includes('export type RequiredAttributeNames<T extends AvailableElement> ='))
		assert.ok(
			source.includes('export type OptionalAttributeNames<T extends AvailableElement> = Exclude<'),
		)
	})
})

describe('emitTypesSource - values typed by their datatype', () => {
	const typed: DefinitionData = {
		Root: {
			parents: [],
			attributes: {
				sequence: ['color', 'either', 'name', 'names', 'nameOrInt', 'plain'],
				details: {
					color: { type: { builtin: 'token', facets: { enumeration: ['red', 'blue'] } } },
					either: {
						type: {
							union: [{ builtin: 'int' }, { builtin: 'token', facets: { enumeration: ['none'] } }],
						},
					},
					name: { type: { builtin: 'QName', facets: { enumeration: ['{urn:t}here'] } } },
					names: { type: { list: { builtin: 'QName' }, facets: { enumeration: ['t:x t:y'] } } },
					nameOrInt: {
						type: {
							union: [{ builtin: 'QName' }, { builtin: 'int' }],
							facets: { enumeration: ['t:x'] },
						},
					},
					plain: { type: { builtin: 'int' } },
				},
			},
			children: { sequence: [], details: {} },
		},
	}
	const source = emitTypesSource({ definition: typed, typedValues: true })

	const expectedLines: Record<string, string> = {
		'an enumeration in the datatype -> the union of its values, open to others':
			"\tcolor?: 'red' | 'blue' | (string & {})",
		'a union whose members enumerate values -> those values, open to others':
			"\teither?: 'none' | (string & {})",
		'an enumeration of qualified names -> a string, the values are not what is written':
			'\tname?: string',
		'a datatype without enumeration -> a string': '\tplain?: string',
		'a list of qualified names, enumerated -> a string, its values depend on prefixes':
			'\tnames?: string',
		'a union holding qualified names, enumerated -> a string': '\tnameOrInt?: string',
	}
	for (const [name, line] of Object.entries(expectedLines)) {
		it(name, () => assert.ok(source.split('\n').includes(line), `missing line: ${line}`))
	}
})
