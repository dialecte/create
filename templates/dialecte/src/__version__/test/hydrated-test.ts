import {
	assertValid__DialecteName__TestCases,
	assertValid__DialecteName__Xml,
} from './assert-valid-xml'

import { CUSTOM_RECORD_ID_ATTRIBUTE, CUSTOM_RECORD_ID_ATTRIBUTE_NAME } from '@dialecte/core/helpers'
import {
	createTestProject,
	createTestRecordFactory,
	createXmlAssertions,
	createTestRunner,
} from '@dialecte/core/test'

import { __DIALECTE_NAME___DIALECTE_CONFIG } from '@/__version__/config'
import { __DIALECTE_NAME___EXTENSION_MODULES } from '@/__version__/extensions'

import type { __DialecteName__Test } from './hydrated-test.types'
import type { Config } from '@/__version__/config/dialecte.config'

export { ALL_XMLNS_NAMESPACES, XMLNS___DIALECTE_NAME___NAMESPACE } from './xmlns.constants'
export { CUSTOM_RECORD_ID_ATTRIBUTE, CUSTOM_RECORD_ID_ATTRIBUTE_NAME }
export { assertValid__DialecteName__Xml } from './assert-valid-xml'

const __DIALECTE_NAME___EXTENSIONS = { base: __DIALECTE_NAME___EXTENSION_MODULES }

const rawRun__DialecteName__TestCases = createTestRunner<Config, __DialecteName__Test.Modules>({
	dialecteConfig: __DIALECTE_NAME___DIALECTE_CONFIG,
	extensions: __DIALECTE_NAME___EXTENSIONS,
})

/**
 * `createTestRunner`, wrapped so the XML of every case is checked against the schema before the
 * suite runs: a mistyped tag, a wrong namespace or an unknown attribute fails loudly, every invalid
 * case reported at once, instead of the suite quietly testing something else.
 */
export const run__DialecteName__TestCases: typeof rawRun__DialecteName__TestCases = {
	...rawRun__DialecteName__TestCases,
	withExport(params) {
		assertValid__DialecteName__TestCases({ testCases: params.testCases })
		rawRun__DialecteName__TestCases.withExport(params)
	},
	withoutExport(params) {
		assertValid__DialecteName__TestCases({ testCases: params.testCases })
		rawRun__DialecteName__TestCases.withoutExport(params)
	},
}

/**
 * A __DialecteName__ project opened on the given XML, its structure checked against the schema first (required
 * attributes may be left out). Opened inside a running test, the project is destroyed when the test ends; opened
 * outside one (`beforeAll`), the caller destroys it.
 *
 * @intent open a test project on a fixture XML
 */
export async function create__DialecteName__TestProject(params: {
	sourceXml: string
	targetXml?: string
}) {
	const { sourceXml, targetXml } = params
	// a fixture may leave out required attributes; its structure must still be the schema's
	assertValid__DialecteName__Xml({ xml: sourceXml, label: 'sourceXml', requireComplete: false })
	if (targetXml)
		assertValid__DialecteName__Xml({ xml: targetXml, label: 'targetXml', requireComplete: false })

	return createTestProject<Config, __DialecteName__Test.Modules>({
		sourceXml,
		targetXml,
		dialecteConfig: __DIALECTE_NAME___DIALECTE_CONFIG,
		extensions: __DIALECTE_NAME___EXTENSIONS,
	})
}

/**
 * Builds a raw (default), tracked or tree record of the __DialecteName__ definition from its tag and fields, as
 * core stores it, without opening a project.
 *
 * @intent build one typed record for a test without opening a project
 */
export const create__DialecteName__TestRecord: ReturnType<typeof createTestRecordFactory<Config>> =
	createTestRecordFactory<Config>(__DIALECTE_NAME___DIALECTE_CONFIG)

const xmlAssertions = createXmlAssertions({
	namespaces: __DIALECTE_NAME___DIALECTE_CONFIG.namespaces,
})

/**
 * Asserts that each XPath query selects at least one node of the XML text; the prefixes are the
 * __DialecteName__ namespace keys.
 *
 * @intent assert that an exported XML holds the elements XPath queries select
 */
export const assertExpectedElementQueries = xmlAssertions.assertExpectedElementQueries

/**
 * Asserts that no XPath query selects a node of the XML text, while every step but the last still does; the
 * prefixes are the __DialecteName__ namespace keys.
 *
 * @intent assert that an exported XML no longer holds an element
 */
export const assertUnexpectedElementQueries = xmlAssertions.assertUnexpectedElementQueries
