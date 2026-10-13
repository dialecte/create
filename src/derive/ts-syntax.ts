/** TypeScript source fragments, written the way the dialectes' formatter keeps them. */

/** A single-quoted string literal. */
export function tsString(value: string): string {
	const escaped = value
		.replaceAll('\\', '\\\\')
		.replaceAll("'", "\\'")
		.replaceAll('\n', '\\n')
		.replaceAll('\r', '\\r')
		.replaceAll('\t', '\\t')
	return `'${escaped}'`
}

/** An object key: bare when it is an identifier, quoted otherwise (`'eIEC61850-6-100:version'`). */
export function tsKey(name: string): string {
	return isIdentifier(name) ? name : tsString(name)
}

/** `.name`, or `['a-b']` for a name that is not an identifier. */
export function tsMember(name: string): string {
	return isIdentifier(name) ? `.${name}` : `[${tsString(name)}]`
}

export function tsStringArray(items: readonly string[]): string {
	return `[${items.map(tsString).join(', ')}]`
}

/** A `Record<string, readonly string[]>` literal, keys sorted. */
export function tsRecord(data: Readonly<Record<string, readonly string[]>>): string {
	const keys = Object.keys(data).sort()
	if (keys.length === 0) return '{}'
	const lines = keys.map((key) => `\t${tsKey(key)}: ${tsStringArray(data[key] ?? [])},`)
	return ['{', ...lines, '}'].join('\n')
}

/**
 * A unique TS identifier for every element name, to build type names from. A name that already is
 * an identifier is kept; the others become PascalCase, and a clash takes a numeric suffix.
 */
export function deriveTypeNames(names: readonly string[]): ReadonlyMap<string, string> {
	const typeNames = new Map<string, string>()
	const taken = new Set<string>()
	for (const name of names.filter(isIdentifier)) {
		typeNames.set(name, name)
		taken.add(name)
	}
	for (const name of names.filter((candidate) => !isIdentifier(candidate)).sort()) {
		const candidate = toPascalCase(name)
		let unique = candidate
		for (let suffix = 2; taken.has(unique); suffix++) unique = `${candidate}_${suffix}`
		typeNames.set(name, unique)
		taken.add(unique)
	}
	return typeNames
}

/** The type of an element's attributes as declared under a parent: `AttributesPInAddress`. */
export function edgeTypeName(params: {
	typeNames: ReadonlyMap<string, string>
	element: string
	parent: string
}): string {
	const { typeNames, element, parent } = params
	return `Attributes${typeNames.get(element)}In${typeNames.get(parent) ?? toPascalCase(parent)}`
}

/** An identifier as the generator has always read one (Unicode XID, as Python's `str.isidentifier`). */
function isIdentifier(name: string): boolean {
	return /^[\p{XID_Start}_]\p{XID_Continue}*$/u.test(name)
}

/** Any XML name as a TS identifier: `boolean-value` -> `BooleanValue`. */
function toPascalCase(name: string): string {
	const parts = name.split(/[^0-9A-Za-z_]+/).filter((part) => part.length > 0)
	const identifier = parts.map((part) => part[0]?.toUpperCase() + part.slice(1)).join('') || '_'
	return /^\d/.test(identifier) ? `_${identifier}` : identifier
}
