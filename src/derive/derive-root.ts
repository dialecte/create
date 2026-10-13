import type { DefinitionData } from './derive.types.ts'

/**
 * The root of a document: the one root candidate, or the one chosen. A candidate is an element no other element
 * holds - itself excepted, so a root that nests in itself stays one; with one candidate it is taken, with several
 * none is taken silently (a wrong root corrupts every table derived from it). The one chosen may be a candidate or
 * any global element: XSD lets any global element start a document, even one another element holds (FHIR's resources
 * all hold one another).
 */
export function deriveRoot(params: { definition: DefinitionData; chosen?: string }): string {
	const { definition, chosen } = params
	const candidates = Object.entries(definition)
		.filter(([tag, element]) => element.parents.every((parent) => parent === tag))
		.map(([tag]) => tag)
		.sort()
	const globals = Object.entries(definition)
		.filter(([, element]) => element.global === true)
		.map(([tag]) => tag)
		.sort()

	if (chosen !== undefined) {
		if (!candidates.includes(chosen) && !globals.includes(chosen)) {
			throw new Error(
				`'${chosen}' is not a root candidate nor a global element; the candidates are: ${candidates.join(', ')}`,
			)
		}
		return chosen
	}
	const [only, ...others] = candidates
	if (only === undefined) {
		throw new Error(
			`No element starts a document by itself (every one is held by another); choose one with --root among the global elements: ${globals.join(', ')}`,
		)
	}
	if (others.length > 0) {
		throw new Error(`Several elements can start a document; choose one: ${candidates.join(', ')}`)
	}
	return only
}
