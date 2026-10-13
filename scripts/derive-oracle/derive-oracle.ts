import type { DeclarationData, DefinitionData, ElementData } from '../../src/derive/derive.types.ts'
/**
 * The oracle of the derivations: every fact `constants.generated.ts` states, recomputed from the definition by the
 * plainest route there is - never through `src/derive` - and compared. The derivation tests compare with files the
 * same code wrote; this compares with what the definition says.
 */
import type { DerivedFact, Disagreement, EmittedConstants } from './derive-oracle.types.ts'

export function checkDerivation(params: {
	definition: DefinitionData
	constants: EmittedConstants
}): Disagreement[] {
	const { definition, constants } = params
	const tags = Object.keys(definition).sort()
	const children = Object.fromEntries(
		tags.map((tag) => [tag, definition[tag]?.children.sequence ?? []]),
	)
	// what holds an element, read from the holders - not from the definition's own `parents`
	const parents = inverse({ relation: children, tags })
	const descendants = transitive({ relation: children, tags })
	const ancestors = inverse({ relation: descendants, tags })
	// a root: an element nothing holds but itself, or any global element (XSD lets one start a document)
	const candidates = tags.filter(
		(tag) =>
			(parents[tag] ?? []).every((holder) => holder === tag) || definition[tag]?.global === true,
	)
	return [
		...compare({
			fact: 'elements',
			element: '*',
			expected: tags,
			emitted: constants.ELEMENT_NAMES,
		}),
		...(candidates.includes(constants.ROOT_ELEMENT)
			? []
			: [
					{
						fact: 'root' as const,
						element: constants.ROOT_ELEMENT,
						expected: candidates,
						emitted: constants.ROOT_ELEMENT,
					},
				]),
		...tags.flatMap((tag) =>
			compare({
				fact: 'children',
				element: tag,
				expected: children[tag] ?? [],
				emitted: constants.CHILDREN[tag],
			}),
		),
		...tags.flatMap((tag) =>
			compare({
				fact: 'parents',
				element: tag,
				expected: parents[tag] ?? [],
				emitted: constants.PARENTS[tag],
			}),
		),
		...tags.flatMap((tag) =>
			compare({
				fact: 'descendants',
				element: tag,
				expected: descendants[tag] ?? [],
				emitted: constants.DESCENDANTS[tag],
			}),
		),
		...tags.flatMap((tag) =>
			compare({
				fact: 'ancestors',
				element: tag,
				expected: ancestors[tag] ?? [],
				emitted: constants.ANCESTORS[tag],
			}),
		),
		...tags.flatMap((tag) =>
			compare({
				fact: 'attributes',
				element: tag,
				expected: attributeNames({ content: definition[tag] }),
				emitted: keysOf(constants.ATTRIBUTES.byTag[tag]),
			}),
		),
		...tags.flatMap((tag) =>
			compare({
				fact: 'required',
				element: tag,
				expected: Object.entries(definition[tag]?.attributes.details ?? {})
					.filter(([, attribute]) => attribute.required === true)
					.map(([name]) => name)
					.sort(),
				emitted: constants.REQUIRED_ATTRIBUTES[tag],
			}),
		),
		...tags.flatMap((parent) =>
			(children[parent] ?? [])
				.filter((child) => child in definition)
				.flatMap((child) =>
					compare({
						fact: 'attributes-by-parent',
						element: child,
						parent,
						expected: attributeNames({ content: declarationUnder({ definition, parent, child }) }),
						emitted: keysOf(constants.ATTRIBUTES.byParent[parent]?.[child]),
					}),
				),
		),
	]
}

/**
 * The child as its parent holds it: the declaration the parent names when it names one (one namespace, one
 * declaration), else the tag level - the union the record's namespace or matched particle decides from.
 */
export function declarationUnder(params: {
	definition: DefinitionData
	parent: string
	child: string
}): ElementData | DeclarationData | undefined {
	const { definition, parent, child } = params
	const named = Object.values(definition[parent]?.children.details[child]?.declarations ?? {})
	const only = named.length === 1 && named[0]?.length === 1 ? named[0][0] : undefined
	const tagLevel = definition[child]
	return (only === undefined ? undefined : tagLevel?.declarations?.[only]) ?? tagLevel
}

/**
 * The attribute names an element's or a declaration's type offers, sorted: what it declares, and `xsi:type` when it
 * - or, for a tag declared several ways, one of its declarations - may name a type.
 */
export function attributeNames(params: {
	content: ElementData | DeclarationData | undefined
}): string[] {
	const { content } = params
	if (content === undefined) return []
	const ways = 'declarations' in content ? Object.values(content.declarations ?? {}) : []
	const namesType = [content, ...ways].some((way) => (way.variants ?? []).length > 0)
	return [...content.attributes.sequence, ...(namesType ? ['xsi:type'] : [])].sort()
}

function keysOf(value: object | undefined): string[] | undefined {
	return value === undefined ? undefined : Object.keys(value).sort()
}

/** The transitive closure of a relation, each list sorted: grown until a pass adds nothing. */
function transitive(params: {
	relation: Readonly<Record<string, readonly string[]>>
	tags: readonly string[]
}): Record<string, string[]> {
	const { relation, tags } = params
	const reached = new Map(tags.map((tag) => [tag, new Set(relation[tag] ?? [])]))
	let grew = true
	while (grew) {
		grew = false
		for (const set of reached.values()) {
			for (const step of set) {
				for (const next of reached.get(step) ?? []) {
					if (!set.has(next)) {
						set.add(next)
						grew = true
					}
				}
			}
		}
	}
	return Object.fromEntries(tags.map((tag) => [tag, [...(reached.get(tag) ?? [])].sort()]))
}

/** The inverse of a relation over `tags`, each list sorted: `y` lists `x` when `x` lists `y`. */
function inverse(params: {
	relation: Readonly<Record<string, readonly string[]>>
	tags: readonly string[]
}): Record<string, string[]> {
	const { relation, tags } = params
	return Object.fromEntries(
		tags.map((tag) => [tag, tags.filter((holder) => relation[holder]?.includes(tag)).sort()]),
	)
}

/** A disagreement when the two lists differ, order included. */
function compare(params: {
	fact: DerivedFact
	element: string
	parent?: string
	expected: readonly string[]
	emitted: readonly string[] | undefined
}): Disagreement[] {
	const { fact, element, parent, expected, emitted } = params
	if (
		emitted !== undefined &&
		emitted.length === expected.length &&
		emitted.every((item, index) => item === expected[index])
	)
		return []
	return [
		{
			fact,
			element,
			...(parent === undefined ? {} : { parent }),
			expected: [...expected],
			emitted: emitted === undefined ? emitted : [...emitted],
		},
	]
}

/** One line for a report: `agrees`, or how many disagreements and the first few. */
export function describeDisagreements(params: { disagreements: readonly Disagreement[] }): string {
	const { disagreements } = params
	if (disagreements.length === 0) return 'agrees with the definition'
	const shown = disagreements
		.slice(0, 5)
		.map(
			({ fact, element, parent, expected, emitted }) =>
				`${fact} ${parent === undefined ? '' : `${parent} > `}${element}: expected ${JSON.stringify(expected)}, emitted ${JSON.stringify(emitted)}`,
		)
	return `${disagreements.length} disagreement(s)\n    ${shown.join('\n    ')}`
}
