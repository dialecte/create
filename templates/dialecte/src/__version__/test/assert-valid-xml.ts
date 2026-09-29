import { createXmlSchemaAssertions } from '@dialecte/core/test'

import { __DIALECTE_NAME___DIALECTE_CONFIG } from '@/__version__/config'

/**
 * Structural validation of test fixtures against the schema, bound to this package's generated
 * definition and namespaces. The engine is `createXmlSchemaAssertions` from `@dialecte/core/test`.
 *
 * It asserts that every element's namespace matches its parent context, that every element is an
 * allowed child of its parent, and that every attribute is known to its element. Elements unknown to
 * the schema are skipped, and so is any element in a namespace the package does not declare.
 */
const { assertValidXml, assertValidXmlTestCases } = createXmlSchemaAssertions({
	definition: __DIALECTE_NAME___DIALECTE_CONFIG.definition,
	namespaces: __DIALECTE_NAME___DIALECTE_CONFIG.namespaces,
	schemaName: '__DialecteName__',
})

export const assertValid__DialecteName__Xml = assertValidXml
export const assertValid__DialecteName__TestCases = assertValidXmlTestCases
