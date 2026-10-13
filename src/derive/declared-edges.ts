import { attributeShape } from './xsi-type-shapes.ts'

import type {
	AttributeShape,
	DeclarationData,
	DeclaredEdge,
	DefinitionData,
	LiteralOf,
	TypesData,
} from './derive.types.ts'

/** Every edge whose child carries another attribute type there than at its tag level: each gets a type of its own. */
export function findDeclaredEdges(params: {
	definition: DefinitionData
	types: TypesData
	literalOf: LiteralOf
}): DeclaredEdge[] {
	const { definition } = params
	const edges: DeclaredEdge[] = []
	for (const [parent, element] of Object.entries(definition)) {
		for (const child of Object.keys(element.children.details)) {
			const shape = shapeDeclaredUnder({ ...params, parent, child })
			if (shape !== undefined) edges.push({ parent, child, shape })
		}
	}
	return edges
}

/**
 * The attribute type of `child` under `parent` when it is not its tag level's: the shape of the declaration the
 * edge references (`attributeShape`: its attributes, the types it may name), when they differ (a tag declared two
 * ways by namespace alone keeps one type).
 */
export function shapeDeclaredUnder(params: {
	definition: DefinitionData
	types: TypesData
	literalOf: LiteralOf
	parent: string
	child: string
}): AttributeShape | undefined {
	const { definition, types, literalOf, parent, child } = params
	const declared = declaredUnder({ definition, parent, child })
	const tagLevel = definition[child]
	if (declared === undefined || tagLevel === undefined) return undefined
	const offered = attributeShape({ content: declared, types, literalOf })
	const general = attributeShape({ content: tagLevel, types, literalOf })
	return sameData(typed(offered), typed(general)) ? undefined : offered
}

/** What an attribute type is made of: the attributes and what each is - not which identify the element - and the types. */
function typed(shape: AttributeShape): unknown {
	const { own, variants } = shape
	return {
		own: own && {
			sequence: own.attributes.sequence,
			details: own.attributes.details,
			literals: own.literals,
		},
		variants,
	}
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
