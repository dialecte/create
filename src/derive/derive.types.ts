/**
 * The part of a generated definition the derivations read. Structural on purpose: the derivations
 * depend on the data a definition holds, not on the package that types it.
 */
export type DefinitionData = Readonly<Record<string, ElementData>>

export type ElementData = {
	readonly namespace?: NamespaceData
	/** A global declaration: it may start a document. */
	readonly global?: true
	readonly parents: readonly string[]
	readonly attributes: {
		readonly sequence: readonly string[]
		readonly details: Readonly<Record<string, AttributeData>>
	}
	readonly children: {
		readonly sequence: readonly string[]
		/** A wildcard admits other elements. */
		readonly any?: true
		readonly details: Readonly<Record<string, EdgeData>>
	}
	readonly contentModel?: ParticleData
	/** Each way a tag declared several ways is declared, by number; the tag level is their union. */
	readonly declarations?: Readonly<Record<string, DeclarationData>>
	/** The declared type when it is named (Clark name): an instance may name it with xsi:type too. */
	readonly type?: string
	/** The types an instance may name instead of the declared one with xsi:type (Clark names, in `TYPES`). */
	readonly variants?: readonly string[]
	/** The declared type is abstract (every declaration's, for a tag declared several ways): an instance names another. */
	readonly abstractType?: true
}

/** The types elements may take with xsi:type, by Clark name: what each lets an element hold. */
export type TypesData = Readonly<Record<string, DeclarationData>>

/** The element as one of its declarations has it. */
export type DeclarationData = {
	readonly namespace?: NamespaceData
	readonly attributes: ElementData['attributes']
	readonly children: ElementData['children']
	readonly contentModel?: ParticleData
	readonly type?: string
	readonly variants?: readonly string[]
	readonly abstractType?: true
}

export type AttributeData = {
	/** The namespace of an attribute of another namespace than its element's, keyed `prefix:local`. */
	readonly namespace?: NamespaceData
	readonly required?: true
	readonly fixed?: string
	readonly type?: DataTypeData
}

/** What a simple value is: a built-in, a list of one, a union of several, with the facets restrictions add. */
export type DataTypeData = {
	readonly builtin?: string
	readonly list?: DataTypeData
	readonly union?: readonly DataTypeData[]
	readonly facets?: { readonly enumeration?: readonly string[] }
}

/**
 * A parent → child edge of a child declared several ways: per namespace it is held in there, the numbers of the
 * declarations its particles hold - one decides it, several leave it to the particle matched.
 */
export type EdgeData = {
	readonly declarations: Readonly<Record<string, readonly string[]>>
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

/** A parent → child edge whose child is declared there with attributes of its own. */
export type DeclaredEdge = {
	readonly parent: string
	readonly child: string
	readonly shape: AttributeShape
}

/**
 * What an element's attribute type is made of. Without a type to name instead of its own, its attributes alone;
 * otherwise a union on `xsi:type`: its own member (none when its declared type is abstract) and one per type it may
 * name, each by the literal core stores it as.
 */
export type AttributeShape = {
	readonly own?: {
		readonly attributes: ElementData['attributes']
		/** The literals `xsi:type` may name its own type with; empty when its type cannot be named so. */
		readonly literals: readonly string[]
	}
	/** The types it may name instead, by their stored literal, in the definition's order. */
	readonly variants: readonly VariantMember[]
}

export type VariantMember = {
	/** How core stores `xsi:type` naming the type: `local`, or `prefix:local` outside the default namespace. */
	readonly literal: string
	/** The type's Clark name, its key in `TYPES`. */
	readonly clark: string
	/** The attributes an element taking the type has. */
	readonly attributes: ElementData['attributes']
}

/** The stored literal of a type's Clark name; `undefined` when core keeps it as written (a namespace not declared). */
export type LiteralOf = (clark: string) => string | undefined

export type NamespaceData = { readonly prefix: string; readonly uri: string }

/** What a scaffolded package's worked example is written with: the root, its first child and what that child requires. */
export type ExampleFacts = {
	readonly root: { readonly name: string; readonly namespaceUri: string }
	/** The first child the root allows; `null` when it allows none. */
	readonly child: {
		readonly name: string
		readonly namespaceUri: string
		/** Each attribute the child requires, with a value the schema accepts. */
		readonly requiredAttributes: readonly { readonly name: string; readonly value: string }[]
	} | null
}

/** What generating a definition tells the scaffold: what its worked example is written with, the namespaces to declare. */
export type GeneratedFacts = {
	readonly example: ExampleFacts
	/** The namespaces the definition gives a prefix, beside the default one (`prefixedNamespaces`). */
	readonly namespaces: readonly NamespaceData[]
}

/** Element → element names, each list sorted. */
export type ElementGraph = Readonly<Record<string, readonly string[]>>

export type DerivedGraph = {
	readonly children: ElementGraph
	readonly parents: ElementGraph
	readonly descendants: ElementGraph
	readonly ancestors: ElementGraph
}
