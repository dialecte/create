import type { DeclaredEdge, DefinitionData, EdgeData } from './derive.types.ts'

/**
 * An edge carries its own declaration of the child when it holds attributes and children, both -
 * the rule core's `resolveDefinition` follows: a declaration on an edge is written in full.
 */
export function isDeclaredEdge(
	edge: EdgeData | undefined,
): edge is EdgeData & Required<Pick<EdgeData, 'attributes' | 'children'>> {
	return edge?.attributes !== undefined && edge.children !== undefined
}

/** Every edge that carries its own declaration of the child. */
export function findDeclaredEdges(params: { definition: DefinitionData }): DeclaredEdge[] {
	const { definition } = params
	const edges: DeclaredEdge[] = []
	for (const [parent, element] of Object.entries(definition)) {
		for (const [child, edge] of Object.entries(element.children.details)) {
			if (isDeclaredEdge(edge)) edges.push({ parent, child, attributes: edge.attributes })
		}
	}
	return edges
}

/** The declaration of `child` under `parent`, when that edge carries one. */
export function declaredUnder(params: {
	definition: DefinitionData
	parent: string
	child: string
}): (EdgeData & Required<Pick<EdgeData, 'attributes' | 'children'>>) | undefined {
	const { definition, parent, child } = params
	const edge = definition[parent]?.children.details[child]
	return isDeclaredEdge(edge) ? edge : undefined
}

/** The children of `parent` that are elements of the definition, in the definition's order. */
export function elementChildren(params: { definition: DefinitionData; parent: string }): string[] {
	const { definition, parent } = params
	return (definition[parent]?.children.sequence ?? []).filter((child) => child in definition)
}
