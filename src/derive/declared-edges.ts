import type {
	DeclarationData,
	DeclaredEdge,
	DefinitionData,
	EdgeData,
	ElementData,
} from './derive.types.ts'

/**
 * An edge carries its own declaration of the child when it holds attributes and children, both -
 * the rule core's `resolveDefinition` follows: a declaration on an edge is written in full.
 */
export function isDeclaredEdge(
	edge: EdgeData | undefined,
): edge is EdgeData & Required<Pick<EdgeData, 'attributes' | 'children'>> {
	return edge?.attributes !== undefined && edge.children !== undefined
}

/** Every edge whose child carries other attributes there than at its tag level: each gets a type of its own. */
export function findDeclaredEdges(params: { definition: DefinitionData }): DeclaredEdge[] {
	const { definition } = params
	const edges: DeclaredEdge[] = []
	for (const [parent, element] of Object.entries(definition)) {
		for (const child of Object.keys(element.children.details)) {
			const attributes = attributesDeclaredUnder({ definition, parent, child })
			if (attributes !== undefined) edges.push({ parent, child, attributes })
		}
	}
	return edges
}

/**
 * The attributes of `child` under `parent` when they are not its tag level's: those of the declaration the edge
 * carries inline (always - the definitions committed before the rebuilt generator), or of the one it references
 * when they differ (a tag declared two ways by namespace alone keeps one type).
 */
export function attributesDeclaredUnder(params: {
	definition: DefinitionData
	parent: string
	child: string
}): ElementData['attributes'] | undefined {
	const { definition, parent, child } = params
	const edge = definition[parent]?.children.details[child]
	if (isDeclaredEdge(edge)) return edge.attributes
	const declared = declaredUnder({ definition, parent, child })
	if (declared === undefined) return undefined
	// what the attribute type is made of: the attributes and what each is, not which identify the element
	return sameData(typed(declared.attributes), typed(definition[child]?.attributes))
		? undefined
		: declared.attributes
}

function typed(attributes: ElementData['attributes'] | undefined): unknown {
	return attributes && { sequence: attributes.sequence, details: attributes.details }
}

/** Whether two pieces of definition data say the same, whatever the order of their keys. */
function sameData(first: unknown, second: unknown): boolean {
	return canonical(first) === canonical(second)
}

function canonical(value: unknown): string {
	return JSON.stringify(value, (_key, item: unknown) =>
		item !== null && typeof item === 'object' && !Array.isArray(item)
			? Object.fromEntries(
					Object.entries(item).sort(([first], [second]) => (first < second ? -1 : 1)),
				)
			: item,
	)
}

/**
 * The declaration of `child` under `parent`, when the edge decides one: the only one it references - one
 * namespace, one id -, or the one it carries inline (the definitions committed before the rebuilt generator).
 * Otherwise none: the namespace or the particle matched decides, the tag level stands for all of them.
 */
export function declaredUnder(params: {
	definition: DefinitionData
	parent: string
	child: string
}): DeclarationData | undefined {
	const { definition, parent, child } = params
	const edge = definition[parent]?.children.details[child]
	if (isDeclaredEdge(edge)) {
		return { attributes: edge.attributes, children: edge.children, contentModel: edge.contentModel }
	}
	const [ids, ...otherNamespaces] = Object.values(edge?.declarations ?? {})
	const [only, ...others] = ids ?? []
	if (only === undefined || others.length > 0 || otherNamespaces.length > 0) return undefined
	return definition[child]?.declarations?.[only]
}

/** The children of `parent` that are elements of the definition, in the definition's order. */
export function elementChildren(params: { definition: DefinitionData; parent: string }): string[] {
	const { definition, parent } = params
	return (definition[parent]?.children.sequence ?? []).filter((child) => child in definition)
}
