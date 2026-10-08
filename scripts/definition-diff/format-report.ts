import type { Difference } from './diff-definitions.types.ts'

/** The differences grouped by category, one line each, readable in a review. */
export function formatReport(params: { differences: readonly Difference[] }): string {
	const { differences } = params
	if (differences.length === 0) return 'no difference\n'

	const byCategory = new Map<string, Difference[]>()
	for (const difference of differences) {
		byCategory.set(difference.category, [
			...(byCategory.get(difference.category) ?? []),
			difference,
		])
	}

	const lines = [`${differences.length} differences`]
	const categories = [...byCategory.keys()].sort()
	for (const category of categories) {
		const group = byCategory.get(category) ?? []
		lines.push('', `## ${category} (${group.length})`)
		for (const difference of group) {
			lines.push(
				`- ${[difference.element, ...difference.path].join('.')}: ${describeChange(difference)}`,
			)
		}
	}
	return `${lines.join('\n')}\n`
}

/**
 * `before -> after`; an element that appears or disappears in one word; for two lists of names,
 * only what one has and the other lacks.
 */
function describeChange(params: Difference): string {
	const { category, before, after } = params
	if (category === 'element' && params.path.length === 0)
		return before === undefined ? 'added' : 'removed'
	if (isScalarList(before) && isScalarList(after)) {
		const added = after.filter((item) => !before.includes(item))
		const removed = before.filter((item) => !after.includes(item))
		if (added.length === 0 && removed.length === 0) return 'same items, other order'
		const parts = [
			...(added.length > 0 ? [`+${JSON.stringify(added)}`] : []),
			...(removed.length > 0 ? [`-${JSON.stringify(removed)}`] : []),
		]
		return parts.join(' ')
	}
	return `${describe(before)} -> ${describe(after)}`
}

function isScalarList(value: unknown): value is readonly (string | number | boolean)[] {
	return Array.isArray(value) && value.every((item) => typeof item !== 'object' || item === null)
}

function describe(value: unknown): string {
	return value === undefined ? '(absent)' : JSON.stringify(value)
}
