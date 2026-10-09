import { enumerated } from './typed-attributes.ts'

import type {
	AttributeData,
	DataTypeData,
	DefinitionData,
	ExampleFacts,
	ParticleData,
} from './derive.types.ts'

/** The value an example gives an attribute when the schema offers none to copy. */
const PLACEHOLDER_VALUE = 'hello-world'

/**
 * What a scaffolded package's worked example is written with, so a reader opens real element names instead of
 * lookups: the root, the first child its content model holds that the definition knows, and the attributes that child requires
 * under the root - each with a value the schema accepts. An attribute of another namespace is keyed `prefix:local`:
 * left to code that knows it.
 */
export function exampleFacts(params: { definition: DefinitionData; root: string }): ExampleFacts {
	const { definition, root } = params
	const rootElement = definition[root]
	const rootFacts = { name: root, namespaceUri: rootElement?.namespace?.uri ?? '' }
	// a child the root's own content model holds: not one only a type it may take with xsi:type holds
	const childName = elementNames(rootElement?.contentModel).find((name) => name in definition)
	if (childName === undefined) return { root: rootFacts, child: null }

	// as the root holds it: a child declared several ways, its first namespace there and the declaration held in it
	const child = definition[childName]
	const [held] = Object.entries(rootElement?.children.details[childName]?.declarations ?? {})
	const declared = held ? child?.declarations?.[held[1][0] ?? ''] : undefined
	const namespaceUri = held?.[0] ?? child?.namespace?.uri ?? ''
	const attributes = (declared ?? child)?.attributes ?? { sequence: [], details: {} }
	return {
		root: rootFacts,
		child: {
			name: childName,
			namespaceUri,
			requiredAttributes: attributes.sequence
				.filter((name) => attributes.details[name]?.required === true && !name.includes(':'))
				.map((name) => ({ name, value: acceptedValue(attributes.details[name] ?? {}) })),
		},
	}
}

/** The names of the elements a content model holds, in its order. */
function elementNames(particle: ParticleData | undefined): string[] {
	if (particle === undefined || particle.kind === 'any') return []
	if (particle.kind === 'element') return [particle.name]
	return particle.particles.flatMap(elementNames)
}

/**
 * The fixed value, else the first value its datatype enumerates, else a value of its built-in type, else a
 * placeholder (a name: what most string types accept). A required attribute has no default.
 */
function acceptedValue(attribute: AttributeData): string {
	return (
		attribute.fixed ??
		enumerated(attribute.type)?.[0] ??
		sampleOf(attribute.type) ??
		PLACEHOLDER_VALUE
	)
}

/** A value of each built-in type a name would not be, its other facets aside. */
const BUILTIN_SAMPLES: Readonly<Record<string, string>> = {
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

/** A value of the datatype's built-in type: a list's item, a union's first member that has one. */
function sampleOf(datatype: DataTypeData | undefined): string | undefined {
	if (datatype === undefined) return undefined
	if (datatype.builtin !== undefined) return BUILTIN_SAMPLES[datatype.builtin]
	if (datatype.list !== undefined) return sampleOf(datatype.list)
	return (datatype.union ?? []).map(sampleOf).find((sample) => sample !== undefined)
}
