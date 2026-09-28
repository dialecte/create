const SCHEMA_OPENING_TAG = /<(?:[\w.-]+:)?schema\b[^>]*>/
const TARGET_NAMESPACE = /\btargetNamespace\s*=\s*(?:"([^"]*)"|'([^']*)')/
const COMMENT_OR_PROLOG = /<!--[\s\S]*?-->|<\?[\s\S]*?\?>|<!DOCTYPE[^>]*>/g

/**
 * The namespace the documents of a schema live in: the `targetNamespace` of its root tag, or an
 * empty string for a schema that declares none. Read from the text so it costs nothing. Comments
 * and the prolog are removed first, so a schema tag quoted in a comment is not taken for the root;
 * the first remaining `schema` tag is the root, since nothing but annotations can precede it.
 */
export function extractTargetNamespace(schemaSource: string): string {
	const withoutComments = schemaSource.replace(COMMENT_OR_PROLOG, '')
	const openingTag = SCHEMA_OPENING_TAG.exec(withoutComments)
	if (openingTag === null) return ''

	const declared = TARGET_NAMESPACE.exec(openingTag[0])
	if (declared === null) return ''

	return decodeXmlEntities(declared[1] ?? declared[2] ?? '')
}

function decodeXmlEntities(value: string): string {
	return value
		.replaceAll('&quot;', '"')
		.replaceAll('&apos;', "'")
		.replaceAll('&lt;', '<')
		.replaceAll('&gt;', '>')
		.replaceAll('&amp;', '&')
}
