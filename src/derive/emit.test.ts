import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { emitConstantsSource } from './emit-constants.ts'
import { emitTypesSource } from './emit-types.ts'

import type { DefinitionData, ElementData, TypesData } from './derive.types.ts'

// A root holding an Address and a PhysConn, both holding a P declared differently under each: the
// tag level is the union, each parent names the declaration it holds.
const pUnderAddress: ElementData['attributes'] = {
	sequence: ['type'],
	details: {
		type: { required: true, type: { builtin: 'token', facets: { enumeration: ['IP', 'MAC'] } } },
	},
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
		namespace: { prefix: '', uri: 'urn:t' },
		parents: [],
		attributes: {
			sequence: ['version', 'id'],
			details: { version: { required: true }, id: { required: true } },
		},
		children: {
			sequence: ['PhysConn', 'Address', 'Empty'],
			details: {},
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
			details: { P: { declarations: { '': ['2'] } } },
		},
	},
	Address: {
		parents: ['Root'],
		attributes: { sequence: [], details: {} },
		children: {
			sequence: ['P'],
			details: { P: { declarations: { '': ['1'] } } },
		},
	},
	// an element without attributes
	Empty: { parents: ['Root'], attributes: { sequence: [], details: {} }, children: noChildren },
	P: {
		parents: ['Address', 'PhysConn'],
		attributes: { sequence: ['type'], details: { type: {} } },
		children: noChildren,
		declarations: {
			// under Address, P may name a type with xsi:type
			'1': {
				attributes: pUnderAddress,
				children: noChildren,
				variants: ['{urn:t}tP_IP', '{urn:t}tP_MAC'],
			},
			'2': { attributes: pUnderPhysConn, children: noChildren },
		},
	},
}

// the types P may name under Address
const types: TypesData = {
	'{urn:t}tP_IP': {
		attributes: { sequence: ['type'], details: { type: { required: true, fixed: 'IP' } } },
		children: noChildren,
	},
	'{urn:t}tP_MAC': {
		attributes: {
			sequence: ['type', 'mac'],
			details: { type: { required: true, fixed: 'MAC' }, mac: { required: true } },
		},
		children: noChildren,
	},
}

describe('emitConstantsSource', () => {
	const source = emitConstantsSource({ definition, root: 'Root', types })

	const expectedLines: Record<string, string> = {
		'the root -> ROOT_ELEMENT': "export const ROOT_ELEMENT = 'Root' as const",
		'a child at most once under the root -> a singleton, a repeatable one not':
			"export const SINGLETON_ELEMENTS = ['Address', 'Empty', 'Root'] as const",
		'the types of the homonyms -> imported, sorted':
			"import type { AvailableElement, AttributesOf, AttributesByParent, AttributesPInAddress, AttributesPInPhysConn } from './types.generated'",
		'an element without attributes -> an empty skeleton typed by its element':
			"\tEmpty: {} as AttributesOf<'Empty'>,",
		'a homonym -> its own skeleton under each parent: xsi:type and what the types it may name add':
			"\t\t\tP: { type: '' as string, 'xsi:type': '' as string, mac: '' as string } as AttributesPInAddress,",
		'an element declared once -> the by-tag object under its parent':
			'\t\t\tAddress: ATTRIBUTES_BY_TAG.Address,',
		'required attributes -> listed for their element, sorted': "\tRoot: ['id', 'version'],",
	}
	for (const [name, line] of Object.entries(expectedLines)) {
		it(name, () => assert.ok(source.split('\n').includes(line), `missing line: ${line}`))
	}
})

describe('emitTypesSource', () => {
	const source = emitTypesSource({ definition, types, root: 'Root' })

	const expectedBlocks: Record<string, string> = {
		'a tag declared several ways -> its own member with the values any declaration accepts, one per type any may name':
			"export type AttributesP =\n\t| {\n\t\t\ttype?: 'IP' | 'MAC' | 'Plug' | (string & {})\n\t\t\t'xsi:type'?: never\n\t  }\n\t| AttributesType_tP_IP\n\t| AttributesType_tP_MAC\n",
		'an enumeration under a parent -> the union of its values; one member per type it may name':
			"export type AttributesPInAddress =\n\t| {\n\t\t\ttype: 'IP' | 'MAC' | (string & {})\n\t\t\t'xsi:type'?: never\n\t  }\n\t| AttributesType_tP_IP\n\t| AttributesType_tP_MAC\n",
		'a type an element may name -> its attributes, xsi:type naming it':
			"export type AttributesType_tP_MAC = {\n\t'xsi:type': 'tP_MAC'\n\ttype: 'MAC'\n\tmac: string\n}",
		'a fixed value under a parent -> its literal':
			"export type AttributesPInPhysConn = {\n\ttype: 'Plug'\n}",
		'a homonym in the parent map -> the type of its declaration there':
			'\tPhysConn: {\n\t\tP: AttributesPInPhysConn\n\t}',
	}
	for (const [name, block] of Object.entries(expectedBlocks)) {
		it(name, () => assert.ok(source.includes(block), `missing block:\n${block}`))
	}

	it('the declarations of a homonym -> one type each, in the order of their parents', () => {
		const [address, physConn] = ['AttributesPInAddress', 'AttributesPInPhysConn'].map((name) =>
			source.indexOf(`export type ${name} =`),
		)
		assert.ok(address !== undefined && address >= 0 && physConn !== undefined && address < physConn)
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
	const source = emitTypesSource({ definition: typed, types: {}, root: 'Root' })

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

describe('emitted order and edge shapes', () => {
	// `definition` lists Root, PhysConn, Address, Empty, P: each table must come out sorted whatever that order
	const constants = emitConstantsSource({ definition, root: 'Root', types }).split('\n')
	const emitted = emitTypesSource({ definition, types, root: 'Root' }).split('\n')
	const order = (lines: string[], wanted: string[]) => wanted.map((line) => lines.indexOf(line))

	it('the attribute skeletons by tag -> sorted by element', () => {
		const positions = order(constants, [
			"\tAddress: {} as AttributesOf<'Address'>,",
			"\tEmpty: {} as AttributesOf<'Empty'>,",
			"\tPhysConn: {} as AttributesOf<'PhysConn'>,",
		])
		assert.ok(
			positions.every((position) => position >= 0),
			`missing a skeleton: ${positions}`,
		)
		assert.deepEqual(
			[...positions].sort((a, b) => a - b),
			positions,
		)
	})

	it('the attribute types -> declared sorted by element', () => {
		const positions = order(emitted, [
			'export type AttributesAddress = {',
			'export type AttributesEmpty = {',
			'export type AttributesP =',
			'export type AttributesPhysConn = {',
			'export type AttributesRoot = {',
		])
		assert.ok(
			positions.every((position) => position >= 0),
			`missing a type: ${positions}`,
		)
		assert.deepEqual(
			[...positions].sort((a, b) => a - b),
			positions,
		)
	})

	it('the attribute types map -> sorted by element', () => {
		const positions = order(emitted, [
			'\tAddress: AttributesAddress',
			'\tP: AttributesP',
			'\tRoot: AttributesRoot',
		])
		assert.ok(
			positions.every((position) => position >= 0),
			`missing an entry: ${positions}`,
		)
		assert.deepEqual(
			[...positions].sort((a, b) => a - b),
			positions,
		)
	})

	it('a homonym declared without attributes under a parent -> an empty skeleton there', () => {
		const bare: DefinitionData = {
			Root: {
				parents: [],
				attributes: noChildren,
				children: { sequence: ['P'], details: { P: { declarations: { '': ['1'] } } } },
			},
			P: {
				parents: ['Root'],
				attributes: { sequence: ['x'], details: { x: {} } },
				children: noChildren,
				declarations: { '1': { attributes: noChildren, children: noChildren } },
			},
		}
		const lines = emitConstantsSource({ definition: bare, root: 'Root', types: {} }).split('\n')
		assert.ok(lines.includes('\t\t\tP: {} as AttributesPInRoot,'), lines.join('\n'))
	})

	it("an attribute fixed to '' -> a string, not an empty literal", () => {
		const fixedEmpty: DefinitionData = {
			Root: {
				parents: [],
				attributes: { sequence: ['x'], details: { x: { fixed: '' } } },
				children: noChildren,
			},
		}
		assert.ok(
			emitTypesSource({ definition: fixedEmpty, types: {}, root: 'Root' })
				.split('\n')
				.includes('\tx?: string'),
		)
	})
})

describe('emitTypesSource - xsi:type unions', () => {
	const DEFAULT = 'urn:default'
	const EXT = 'urn:ext'
	const element = (content: Partial<ElementData>): ElementData => ({
		parents: [],
		attributes: noChildren,
		children: noChildren,
		...content,
	})
	const onlyA: ElementData['attributes'] = { sequence: ['a'], details: { a: { required: true } } }
	const unions: DefinitionData = {
		Root: element({ namespace: { prefix: '', uri: DEFAULT }, attributes: onlyA }),
		Other: element({ namespace: { prefix: 'ext', uri: EXT } }),
		Shape: element({
			attributes: onlyA,
			type: `{${DEFAULT}}tShape`,
			abstractType: true,
			variants: [`{${DEFAULT}}tCircle`, `{${EXT}}tSquare`],
		}),
		Plain: element({
			attributes: onlyA,
			type: `{${DEFAULT}}tPlain`,
			variants: [`{${DEFAULT}}tCircle`],
		}),
		// declared two ways, each with its type: either named by the own member
		Twice: element({
			attributes: onlyA,
			declarations: {
				'1': { attributes: onlyA, children: noChildren, type: `{${DEFAULT}}tOne` },
				'2': {
					attributes: onlyA,
					children: noChildren,
					type: `{${DEFAULT}}tTwo`,
					variants: [`{${DEFAULT}}tCircle`],
				},
			},
		}),
	}
	const unionTypes: TypesData = {
		[`{${DEFAULT}}tCircle`]: {
			attributes: { sequence: ['a', 'r'], details: { a: { required: true }, r: {} } },
			children: noChildren,
		},
		[`{${EXT}}tSquare`]: { attributes: onlyA, children: noChildren },
	}
	const source = emitTypesSource({ definition: unions, types: unionTypes, root: 'Root' })

	const expectedBlocks: Record<string, string> = {
		'an abstract type -> no own member: the types it may name, nothing else':
			'export type AttributesShape = AttributesType_tCircle | AttributesType_ExtTSquare\n',
		'a concrete type -> its own member naming it or nothing, then the types it may name':
			"export type AttributesPlain =\n\t| {\n\t\t\ta: string\n\t\t\t'xsi:type'?: 'tPlain'\n\t  }\n\t| AttributesType_tCircle\n",
		'a type of another namespace -> its prefixed literal':
			"export type AttributesType_ExtTSquare = {\n\t'xsi:type': 'ext:tSquare'\n\ta: string\n}",
		"a tag declared several ways -> its own member names each declaration's type":
			"\t\t\t'xsi:type'?: 'tOne' | 'tTwo'\n",
		'an element naming no other type -> its attributes alone, as ever':
			'export type AttributesRoot = {\n\ta: string\n}',
	}
	for (const [name, block] of Object.entries(expectedBlocks)) {
		it(name, () => assert.ok(source.includes(block), `missing block:\n${block}\nin:\n${source}`))
	}

	it('a type two elements may name -> one type, written once', () => {
		assert.equal(source.split('export type AttributesType_tCircle = {').length, 2)
	})

	it('the optional attribute names -> of every member, not only those all share', () => {
		assert.ok(
			source.includes(
				'\tAttributesOf<T> extends infer Member ? (Member extends unknown ? keyof Member : never) : never,',
			),
		)
	})
})
