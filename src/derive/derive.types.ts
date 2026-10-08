/**
 * The part of a generated definition the derivations read. Structural on purpose: the derivations
 * depend on the data a definition holds, not on the package that types it.
 */
export type DefinitionData = Readonly<Record<string, ElementData>>

export type ElementData = {
	readonly parents: readonly string[]
	readonly attributes: {
		readonly sequence: readonly string[]
		readonly details: Readonly<Record<string, AttributeData>>
	}
	readonly children: {
		readonly sequence: readonly string[]
		readonly details: Readonly<Record<string, EdgeData>>
	}
	readonly contentModel?: ParticleData
	/** Each way a tag declared several ways is declared, by number; the tag level is their union. */
	readonly declarations?: Readonly<Record<string, DeclarationData>>
}

/** The element as one of its declarations has it. */
export type DeclarationData = {
	readonly attributes: ElementData['attributes']
	readonly children: ElementData['children']
	readonly contentModel?: ParticleData
}

export type AttributeData = {
	readonly required?: true
	readonly fixed?: string
	readonly facets?: { readonly enumeration?: readonly string[] }
}

/**
 * A parent → child edge: per namespace the child is held in there, the numbers of the declarations its particles
 * hold - one decides it, several leave it to the particle matched -; or, the form the definitions committed before
 * the rebuilt generator use, the child as declared under that parent, inline.
 */
export type EdgeData = {
	readonly declarations?: Readonly<Record<string, readonly string[]>>
	readonly attributes?: ElementData['attributes']
	readonly children?: ElementData['children']
	readonly contentModel?: ParticleData
	/** The child under this parent per `xsi:type` value, keyed by the type's QName. */
	readonly variants?: Readonly<Record<string, { readonly contentModel?: ParticleData }>>
}

export type ParticleData =
	| {
			readonly kind: 'sequence' | 'choice' | 'all'
			readonly minOccurs?: number
			readonly maxOccurs?: number
			readonly particles: readonly ParticleData[]
	  }
	| {
			readonly kind: 'element'
			readonly name: string
			readonly minOccurs?: number
			readonly maxOccurs?: number
	  }
	| { readonly kind: 'any'; readonly minOccurs?: number; readonly maxOccurs?: number }

/** A parent → child edge that carries the child as declared under that parent (a homonym). */
export type DeclaredEdge = {
	readonly parent: string
	readonly child: string
	readonly attributes: ElementData['attributes']
}

/** Element → element names, each list sorted. */
export type ElementGraph = Readonly<Record<string, readonly string[]>>

export type DerivedGraph = {
	readonly children: ElementGraph
	readonly parents: ElementGraph
	readonly descendants: ElementGraph
	readonly ancestors: ElementGraph
}
