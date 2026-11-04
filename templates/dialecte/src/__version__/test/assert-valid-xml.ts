import { createXmlSchemaAssertions } from '@dialecte/core/test'

import { __DIALECTE_NAME___DIALECTE_CONFIG } from '@/__version__/config'

/**
 * Structural validation of test fixtures against the schema, bound to this package's generated
 * definition and namespaces. The engine is `createXmlSchemaAssertions` from `@dialecte/core/test`.
 *
 * It asserts that every element's namespace matches its parent context, that every element is an
 * allowed child of its parent, and that every attribute is known to its element - as declared there, and
 * as the type it names with xsi:type says. Elements unknown to
 * the schema are skipped, and so is any element in a namespace the package does not declare.
 */
const { assertValidXml, assertValidXmlTestCases } = createXmlSchemaAssertions({
	definition: __DIALECTE_NAME___DIALECTE_CONFIG.definition,
	types: __DIALECTE_NAME___DIALECTE_CONFIG.types,
	namespaces: __DIALECTE_NAME___DIALECTE_CONFIG.namespaces,
	schemaName: '__DialecteName__',
})

/**
 * Throws when the XML breaks the structure of the __DialecteName__ schema: an element in the wrong namespace, a child
 * its parent does not allow, an unknown attribute or, unless `requireComplete: false`, a missing required attribute.
 * It is not a full XSD validation: child order, occurrence counts and attribute values are not checked.
 *
 * @intent check that a test fixture follows the __DialecteName__ schema before a test reads it
 */
export const assertValid__DialecteName__Xml = assertValidXml
export const assertValid__DialecteName__TestCases = assertValidXmlTestCases
