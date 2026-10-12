import type { DefinitionData, Difference, DifferenceCategory } from './diff-definitions.types.ts'

/**
 * Every fact that differs between two definitions, element by element. Objects are compared key
 * by key (sorted, so the order is stable); arrays and scalars as whole values, reported at the
 * deepest key that differs.
 */
export function diffDefinitions(params: {
	before: DefinitionData
	after: DefinitionData
	beforeTypes?: DefinitionData
	afterTypes?: DefinitionData
}): Difference[] {
	const { before, after, beforeTypes = {}, afterTypes = {} } = params
	const differences: Difference[] = []
	for (const element of unionOfKeys({ before, after })) {
		collectDifferences({
			element,
			path: [],
			before: before[element],
			after: after[element],
			differences,
		})
	}
	// the types elements may take with xsi:type: each difference filed under them, keyed by the type's name
	const typeDifferences: Difference[] = []
	for (const name of unionOfKeys({ before: beforeTypes, after: afterTypes })) {
		collectDifferences({
			element: name,
			path: [],
			before: beforeTypes[name],
			after: afterTypes[name],
			differences: typeDifferences,
		})
	}
	return [
		...differences,
		...typeDifferences.map((difference) => ({ ...difference, category: 'types' as const })),
	]
}

function collectDifferences(params: {
	element: string
	path: readonly string[]
	before: unknown
	after: unknown
	differences: Difference[]
}): void {
	const { element, path, before, after, differences } = params
	if (isPlainObject(before) && isPlainObject(after)) {
		for (const key of unionOfKeys({ before, after })) {
			collectDifferences({
				element,
				path: [...path, key],
				before: before[key],
				after: after[key],
				differences,
			})
		}
		return
	}
	if (isSameValue(asCompared({ path, value: before }), asCompared({ path, value: after }))) return
	differences.push({ element, path, category: categoryOf(path), before, after })
}

/** Lists whose order says nothing: compared as sets. */
const SET_VALUED_PATHS: readonly string[] = ['parents']

function asCompared(params: { path: readonly string[]; value: unknown }): unknown {
	const { path, value } = params
	const isSetValued = path.length === 1 && SET_VALUED_PATHS.includes(path[0] ?? '')
	return isSetValued && Array.isArray(value) ? [...value].sort() : value
}

/** What a difference is about, read from where it sits in an element's definition. */
function categoryOf(path: readonly string[]): DifferenceCategory {
	const [section, second, third, fourth] = path
	if (section === undefined || section === 'tag') return 'element'
	if (section === 'namespace') return 'namespace'
	if (section === 'documentation') return 'documentation'
	if (section === 'nillable') return 'text-content'
	if (section === 'parents') return 'parents'
	if (section === 'declarations') return 'declarations'
	if (section === 'global') return 'global'
	// what xsi:type may name: the declared type, the variants, and whether one must be named
	if (section === 'type' || section === 'variants' || section === 'abstractType') return 'variants'
	if (section === 'contentModel') return 'content-model'
	if (section === 'constraints') return 'constraints'
	if (section === 'textContent') return isValueFacet(second) ? 'facets' : 'text-content'
	if (section === 'attributes') {
		if (second === 'identityFields') return 'identity-fields'
		if (second !== 'details' || third === undefined) return 'attributes'
		if (third === 'xsi:type') return 'xsi-type'
		return isValueFacet(fourth) ? 'facets' : 'attributes'
	}
	if (section === 'children') {
		if (second !== 'details' || fourth === undefined) return 'children'
		return CHILD_EDGE_CATEGORIES[fourth] ?? 'other'
	}
	return 'other'
}

/** Where a fact of a parent → child edge belongs. */
const CHILD_EDGE_CATEGORIES: Readonly<Record<string, DifferenceCategory>> = {
	required: 'occurrence',
	minOccurs: 'occurrence',
	maxOccurs: 'occurrence',
	namespace: 'namespace',
	constraints: 'constraints',
	variants: 'xsi-type',
	declarations: 'declarations',
	nillable: 'edge-definition',
	attributes: 'edge-definition',
	children: 'edge-definition',
	contentModel: 'edge-definition',
	textContent: 'edge-definition',
}

/** What constrains a value: its facets and its datatype. */
function isValueFacet(key: string | undefined): boolean {
	return key === 'facets' || key === 'type'
}

function unionOfKeys(params: {
	before: Readonly<Record<string, unknown>>
	after: Readonly<Record<string, unknown>>
}): string[] {
	const { before, after } = params
	return [...new Set([...Object.keys(before), ...Object.keys(after)])].sort()
}

function isPlainObject(value: unknown): value is Readonly<Record<string, unknown>> {
	return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Deep equality of the JSON-like values a definition holds, whatever the order of their keys. */
function isSameValue(first: unknown, second: unknown): boolean {
	return canonicalJson(first) === canonicalJson(second)
}

function canonicalJson(value: unknown): string {
	return JSON.stringify(value, function sortKeys(_key, nested: unknown) {
		if (!isPlainObject(nested)) return nested
		return Object.fromEntries(
			Object.entries(nested).sort(([first], [second]) => (first < second ? -1 : 1)),
		)
	})
}
