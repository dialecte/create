import { typedAttributes } from './typed-attributes.ts'

import type { DeclarationData, DeclaredEdge, DefinitionData, ElementData } from './derive.types.ts'

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
 * The attributes of `child` under `parent` when they are not its tag level's: those the declaration the edge
 * references offers (`typedAttributes`: its `xsi:type` included), when they differ (a tag declared two ways by
 * namespace alone keeps one type).
 */
export function attributesDeclaredUnder(params: {
	definition: DefinitionData
	parent: string
	child: string
}): ElementData['attributes'] | undefined {
	const { definition, parent, child } = params
	const declared = declaredUnder({ definition, parent, child })
	const tagLevel = definition[child]
	if (declared === undefined || tagLevel === undefined) return undefined
	const offered = typedAttributes(declared)
	// what the attribute type is made of: the attributes and what each is, not which identify the element
	return sameData(typed(offered), typed(typedAttributes(tagLevel))) ? undefined : offered
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
 * namespace, one id. Otherwise none: the namespace or the particle matched decides, the tag level stands for all of them.
 */
export function declaredUnder(params: {
	definition: DefinitionData
	parent: string
	child: string
}): DeclarationData | undefined {
	const { definition, parent, child } = params
	const edge = definition[parent]?.children.details[child]
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
