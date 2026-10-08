import { declaredUnder } from './declared-edges.ts'

import type { DefinitionData, ParticleData } from './derive.types.ts'

/**
 * The elements a document holds at most once: the root, and every element that occurs at most once
 * under each of its parents when those parents are themselves singletons. How often a child occurs
 * under a parent is read from the content models that apply there - the one declared under each
 * grandparent (or the tag level's), and each `xsi:type` variant's - never from a flat child table,
 * which cannot see a repeating group. A child none of them names (admitted by a wildcard) may occur
 * any number of times. A root that can nest in itself makes nothing a singleton.
 */
export function deriveSingletons(params: { definition: DefinitionData; root: string }): string[] {
	const { definition, root } = params
	if (canNestInItself({ definition, tag: root })) return []

	const singletons = new Set<string>([root])
	const occurrencesByModel = new Map<ParticleData | undefined, ReadonlyMap<string, number>>()

	/**
	 * The most times `child` occurs under `parent`, whichever content model applies there. A model
	 * that does not name the child holds it 0 times - unless it has a wildcard, or there is no model,
	 * which may admit it any number of times; a child no model names at all is unbounded.
	 */
	function maxOccursUnder(parent: string, child: string): number {
		let most = 0
		let named = false
		for (const contentModel of contentModelsOf(parent)) {
			let occurrences = occurrencesByModel.get(contentModel)
			if (occurrences === undefined) {
				occurrences = contentModel === undefined ? new Map() : occurrencesIn(contentModel)
				occurrencesByModel.set(contentModel, occurrences)
			}
			const count = occurrences.get(child)
			if (count !== undefined) named = true
			const opensToOthers = contentModel === undefined || (occurrences.get(WILDCARD) ?? 0) > 0
			most = Math.max(most, count ?? (opensToOthers ? Number.POSITIVE_INFINITY : 0))
		}
		return named ? most : Number.POSITIVE_INFINITY
	}

	/** Every content model `parent` may hold: as declared under each of its parents, and per variant. */
	function contentModelsOf(parent: string): Set<ParticleData | undefined> {
		const element = definition[parent]
		if (element === undefined) return new Set([undefined])
		const models = new Set<ParticleData | undefined>()
		if (element.parents.length === 0) models.add(element.contentModel)
		for (const grandparent of element.parents) {
			const declared = declaredUnder({ definition, parent: grandparent, child: parent })
			models.add(declared?.contentModel ?? element.contentModel)
			const variants = definition[grandparent]?.children.details[parent]?.variants ?? {}
			for (const variant of Object.values(variants)) models.add(variant.contentModel)
		}
		return models
	}

	let grew = true
	while (grew) {
		grew = false
		for (const [tag, element] of Object.entries(definition)) {
			if (singletons.has(tag) || element.parents.length === 0) continue
			const once = element.parents.every(
				(parent) => singletons.has(parent) && maxOccursUnder(parent, tag) <= 1,
			)
			if (once) {
				singletons.add(tag)
				grew = true
			}
		}
	}
	return [...singletons].sort()
}

/**
 * For one occurrence of `particle`, the most times each element it names can occur: a sequence or
 * an `all` holds each of its particles (their counts add up), a choice holds one of them (the
 * largest count wins); a group's own maximum multiplies what it holds.
 */
function occurrencesIn(particle: ParticleData): ReadonlyMap<string, number> {
	if (particle.kind === 'any') return new Map([[WILDCARD, maxOf(particle.maxOccurs)]])
	if (particle.kind === 'element') return new Map([[particle.name, maxOf(particle.maxOccurs)]])

	const combined = new Map<string, number>()
	for (const nested of particle.particles) {
		for (const [name, count] of occurrencesIn(nested)) {
			const current = combined.get(name) ?? 0
			combined.set(name, particle.kind === 'choice' ? Math.max(current, count) : current + count)
		}
	}
	const groupMax = maxOf(particle.maxOccurs)
	return new Map([...combined].map(([name, count]) => [name, times(count, groupMax)]))
}

/** The key under which `occurrencesIn` counts the wildcards of a content model (no element name has a space). */
const WILDCARD = '#any wildcard'

/** Whether `tag` can appear inside itself, at any depth. */
function canNestInItself(params: { definition: DefinitionData; tag: string }): boolean {
	const { definition, tag } = params
	const reached = new Set<string>()
	const pending = [...(definition[tag]?.parents ?? [])]
	while (pending.length > 0) {
		const next = pending.pop()
		if (next === undefined || reached.has(next)) continue
		if (next === tag) return true
		reached.add(next)
		pending.push(...(definition[next]?.parents ?? []))
	}
	return false
}

/** A product of maxima where a prohibited particle (`maxOccurs="0"`) stays prohibited, even in an unbounded group. */
function times(first: number, second: number): number {
	return first === 0 || second === 0 ? 0 : first * second
}

/** An absent maximum is unbounded (the definition writes `maxOccurs` only when it is bounded). */
function maxOf(max: number | undefined): number {
	return max ?? Number.POSITIVE_INFINITY
}
