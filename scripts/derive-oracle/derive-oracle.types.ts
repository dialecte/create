/** The constants a dialecte's `constants.generated.ts` exports, as values: what the oracle checks. */
export type EmittedConstants = {
	readonly ELEMENT_NAMES: readonly string[]
	readonly CHILDREN: Readonly<Record<string, readonly string[]>>
	readonly PARENTS: Readonly<Record<string, readonly string[]>>
	readonly DESCENDANTS: Readonly<Record<string, readonly string[]>>
	readonly ANCESTORS: Readonly<Record<string, readonly string[]>>
	readonly ROOT_ELEMENT: string
	readonly ATTRIBUTES: {
		readonly byTag: Readonly<Record<string, object>>
		readonly byParent: Readonly<Record<string, Readonly<Record<string, object>>>>
	}
	readonly REQUIRED_ATTRIBUTES: Readonly<Record<string, readonly string[]>>
}

/** A fact the emitted constants state that the definition does not imply. */
export type DerivedFact =
	| 'elements'
	| 'children'
	| 'parents'
	| 'descendants'
	| 'ancestors'
	| 'root'
	| 'attributes'
	| 'attributes-by-parent'
	| 'required'

export type Disagreement = {
	readonly fact: DerivedFact
	readonly element: string
	/** For a per-parent fact: the parent it is stated under. */
	readonly parent?: string
	/** What the definition implies, and what the constants say. */
	readonly expected: unknown
	readonly emitted: unknown
}
