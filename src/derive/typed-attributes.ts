import type { AttributeData, DataTypeData, DeclarationData, ElementData } from './derive.types.ts'

/** The attribute a document names a type with, instead of the declared one; written with the `xsi` prefix. */
const XSI_TYPE = 'xsi:type'

/**
 * The attributes an attribute type offers for an element, its declaration, or a tag declared several ways - what
 * the generated types and the attribute skeletons are both made of:
 * - its own attributes; for a tag declared several ways, the values any declaration accepts as hints, where the
 *   union (lenient) types none;
 * - an optional `xsi:type` where the element may name a type instead of its own: the definition declares no such
 *   attribute (XSD gives it to every element), the types it may name are the hints.
 */
export function typedAttributes(content: ElementData | DeclarationData): ElementData['attributes'] {
	const declarations = 'declarations' in content ? Object.values(content.declarations ?? {}) : []
	// the values its declarations accept, as hints - none to add for a tag declared one way
	const own = withDeclaredValues({ content, declarations })
	const variants = [
		...new Set([
			...(content.variants ?? []),
			...declarations.flatMap((declaration) => declaration.variants ?? []),
		]),
	]
	if (variants.length === 0) return own
	return {
		...own,
		sequence: [...own.sequence, XSI_TYPE],
		details: {
			...own.details,
			[XSI_TYPE]: { type: { facets: { enumeration: variants.map(localName) } } },
		},
	}
}

/**
 * The values a datatype enumerates: its own enumeration, else those its union members enumerate (hints - the type
 * stays open). A qualified name's values are written `{uri}local`, never what a document holds: none.
 */
export function enumerated(datatype: DataTypeData | undefined): readonly string[] {
	if (datatype === undefined || holdsQualifiedNames(datatype)) return []
	if (datatype.facets?.enumeration !== undefined) return datatype.facets.enumeration
	return [...new Set((datatype.union ?? []).flatMap(enumerated))]
}

/** Whether the datatype's values are, or hold, qualified names: their written form depends on prefixes. */
function holdsQualifiedNames(datatype: DataTypeData): boolean {
	if (datatype.builtin === 'QName' || datatype.builtin === 'NOTATION') return true
	if (datatype.list !== undefined) return holdsQualifiedNames(datatype.list)
	return (datatype.union ?? []).some(holdsQualifiedNames)
}

/** The tag level's attributes, an attribute it types no value of hinting the values its declarations accept. */
function withDeclaredValues(params: {
	content: ElementData | DeclarationData
	declarations: readonly DeclarationData[]
}): ElementData['attributes'] {
	const { content, declarations } = params
	const details: Record<string, AttributeData> = { ...content.attributes.details }
	for (const name of content.attributes.sequence) {
		const attribute = content.attributes.details[name] ?? {}
		if (attribute.type !== undefined || attribute.fixed !== undefined) continue
		const hints = acceptedValues({ name, declarations })
		if (hints.length > 0) details[name] = { ...attribute, type: { facets: { enumeration: hints } } }
	}
	return { ...content.attributes, details }
}

/** The values the declarations carrying an attribute accept for it: their fixed value, else what they enumerate. */
function acceptedValues(params: {
	name: string
	declarations: readonly DeclarationData[]
}): string[] {
	const { name, declarations } = params
	const values = declarations.flatMap((declaration) => {
		const attribute = declaration.attributes.details[name]
		if (attribute === undefined) return []
		return attribute.fixed !== undefined ? [attribute.fixed] : enumerated(attribute.type)
	})
	return [...new Set(values)]
}

/** `{uri}local` -> `local`: what a document writes in the default namespace. */
function localName(clarkName: string): string {
	return clarkName.replace(/^\{[^}]*\}/, '')
}
