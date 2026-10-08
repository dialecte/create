import type { DefinitionData } from './derive.types.ts'

/**
 * The root of a document: the one root candidate, or the one chosen among several. A candidate is
 * an element no other element holds - itself excepted, so a root that nests in itself stays one.
 * Several candidates are never decided silently: a wrong root corrupts every table derived from it.
 */
export function deriveRoot(params: { definition: DefinitionData; chosen?: string }): string {
	const { definition, chosen } = params
	const candidates = Object.entries(definition)
		.filter(([tag, element]) => element.parents.every((parent) => parent === tag))
		.map(([tag]) => tag)
		.sort()

	if (chosen !== undefined) {
		if (!candidates.includes(chosen)) {
			throw new Error(
				`'${chosen}' is not a root candidate; the candidates are: ${candidates.join(', ')}`,
			)
		}
		return chosen
	}
	const [only, ...others] = candidates
	if (only === undefined) throw new Error('No root candidate: every element is held by another')
	if (others.length > 0) {
		throw new Error(`Several elements can start a document; choose one: ${candidates.join(', ')}`)
	}
	return only
}
