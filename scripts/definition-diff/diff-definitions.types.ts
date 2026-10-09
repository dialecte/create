/** A generated definition read back as plain data: element tag → its definition. */
export type DefinitionData = Readonly<Record<string, unknown>>

/** What a difference is about, read from where it sits in an element's definition. */
export type DifferenceCategory =
	| 'element'
	| 'namespace'
	| 'parents'
	| 'attributes'
	| 'facets'
	| 'xsi-type'
	| 'children'
	| 'occurrence'
	| 'edge-definition'
	| 'declarations'
	| 'global'
	| 'variants'
	| 'types'
	| 'content-model'
	| 'constraints'
	| 'identity-fields'
	| 'text-content'
	| 'documentation'
	| 'other'

/** One fact that differs between two definitions, addressed by element and path. */
export type Difference = {
	element: string
	/** Keys from the element's definition down to the differing value, e.g. `['attributes', 'details', 'name', 'facets']`. */
	path: readonly string[]
	category: DifferenceCategory
	/** `undefined` when absent on that side. */
	before: unknown
	after: unknown
}
