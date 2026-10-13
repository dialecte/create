import { typedAttributes } from './typed-attributes.ts'

import type {
	AttributeShape,
	DeclarationData,
	DefinitionData,
	ElementData,
	LiteralOf,
	NamespaceData,
	TypesData,
	VariantMember,
} from './derive.types.ts'

/** The attribute a document names a type with, instead of the declared one; written with the `xsi` prefix. */
export const XSI_TYPE = 'xsi:type'

/**
 * How core stores an `xsi:type` value naming each type (its canonical form): the local name in the dialecte's
 * default namespace - the root's - and `prefix:local` in another namespace it declares. The definition's prefixes
 * are the ones a dialecte declares (its config is checked against them); a namespace none of its elements or
 * attributes is in has no prefix there, and core keeps such a value as written: no literal to type it with.
 */
export function xsiTypeLiterals(params: { definition: DefinitionData; root: string }): LiteralOf {
	const { definition, root } = params
	const defaultUri = definition[root]?.namespace?.uri ?? ''
	const prefixes = new Map(
		prefixedNamespaces({ definition, root }).map((namespace) => [namespace.uri, namespace.prefix]),
	)
	return function literalOf(clark) {
		// a local name holds no brace: `}` closes the namespace of a Clark name, when it has one
		const closing = clark.indexOf('}')
		const uri = closing === -1 ? '' : clark.slice(1, closing)
		const local = clark.slice(closing + 1)
		if (uri === defaultUri) return local
		const prefix = prefixes.get(uri)
		return prefix === undefined ? undefined : `${prefix}:${local}`
	}
}

/**
 * What an element's - or one of its declarations' - attribute type is made of (`AttributeShape`), as core admits
 * `xsi:type` there: the declared type unless abstract, and the variants; for a tag declared several ways, those of
 * every declaration. A type core cannot store by a literal is left out; so is the own member of an abstract type,
 * unless no variant is left to stand for it, and an own literal a variant member types already (a tag declared
 * several ways: one declaration's type, another's variant).
 */
export function attributeShape(params: {
	content: ElementData | DeclarationData
	types: TypesData
	literalOf: LiteralOf
}): AttributeShape {
	const { content, types, literalOf } = params
	const ways = [
		content,
		...('declarations' in content ? Object.values(content.declarations ?? {}) : []),
	]
	const variants = new Map<string, VariantMember>()
	for (const clark of ways.flatMap((way) => way.variants ?? [])) {
		const literal = literalOf(clark)
		const type = types[clark]
		if (literal !== undefined && type !== undefined) {
			variants.set(literal, { literal, clark, attributes: type.attributes })
		}
	}
	const attributes = typedAttributes(content)
	if (variants.size === 0) return { own: { attributes, literals: [] }, variants: [] }
	// a type with a member of its own is typed there, with its attributes - not by the lenient own member
	const literals = new Set<string>()
	for (const way of ways) {
		const literal = way.type === undefined || way.abstractType ? undefined : literalOf(way.type)
		if (literal !== undefined && !variants.has(literal)) literals.add(literal)
	}
	return {
		...(content.abstractType ? {} : { own: { attributes, literals: [...literals] } }),
		variants: [...variants.values()],
	}
}

/** The attribute names a shape offers, each once: its own, `xsi:type` where it has variants, then what they add. */
export function shapeKeys(params: { shape: AttributeShape }): string[] {
	const { shape } = params
	const keys = new Set(shape.own?.attributes.sequence)
	if (shape.variants.length === 0) return [...keys]
	keys.add(XSI_TYPE)
	for (const { attributes } of shape.variants)
		for (const name of attributes.sequence) keys.add(name)
	return [...keys]
}

/**
 * The namespaces the definition gives a prefix - an element, a declaration or an attribute in each -, once each,
 * sorted by prefix: what a dialecte declares beside its default namespace. The root's namespace is that default one,
 * even where its schema writes it with a prefix (PLC's `ppx`).
 */
export function prefixedNamespaces(params: {
	definition: DefinitionData
	root: string
}): NamespaceData[] {
	const { definition, root } = params
	const defaultUri = definition[root]?.namespace?.uri ?? ''
	const byUri = new Map<string, NamespaceData>()
	for (const element of Object.values(definition)) {
		for (const way of [element, ...Object.values(element.declarations ?? {})]) {
			const namespaces = [
				way.namespace,
				...Object.values(way.attributes.details).map((attribute) => attribute.namespace),
			]
			for (const namespace of namespaces) {
				if (namespace?.prefix && namespace.uri !== defaultUri && !byUri.has(namespace.uri)) {
					byUri.set(namespace.uri, namespace)
				}
			}
		}
	}
	return [...byUri.values()].sort((first, second) => (first.prefix < second.prefix ? -1 : 1))
}
