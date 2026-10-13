import type { DefinitionData, DerivedGraph, ElementGraph } from './derive.types.ts'

/**
 * The child and parent tables of a definition, and their transitive closures. Children keep the
 * definition's order (the order export writes them in); parents and closures are sorted.
 */
export function deriveGraph(params: { definition: DefinitionData }): DerivedGraph {
	const { definition } = params
	const children = mapElements({
		definition,
		read: (element) => [...element.children.sequence],
	})
	const parents = mapElements({ definition, read: (element) => [...element.parents].sort() })
	return {
		children,
		parents,
		descendants: mapElements({
			definition,
			read: (_, tag) => closure({ graph: children, start: tag }),
		}),
		ancestors: mapElements({
			definition,
			read: (_, tag) => closure({ graph: parents, start: tag }),
		}),
	}
}

function mapElements(params: {
	definition: DefinitionData
	read: (element: DefinitionData[string], tag: string) => string[]
}): ElementGraph {
	const { definition, read } = params
	// in the definition's order: the emitter writes every table with its keys sorted (tsRecord)
	return Object.fromEntries(Object.keys(definition).map((tag) => [tag, read(definition[tag], tag)]))
}

/** Every element reachable from `start` through `graph`, `start` itself excluded unless a cycle leads back. */
function closure(params: { graph: ElementGraph; start: string }): string[] {
	const { graph, start } = params
	const reached = new Set<string>()
	const pending = [...(graph[start] ?? [])]
	while (pending.length > 0) {
		const next = pending.pop()
		if (next === undefined || reached.has(next)) continue
		reached.add(next)
		pending.push(...(graph[next] ?? []))
	}
	return [...reached].sort()
}
