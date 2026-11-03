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

export const create__DialecteName__TestRecord: ReturnType<typeof createTestRecordFactory<Config>> =
	createTestRecordFactory<Config>(__DIALECTE_NAME___DIALECTE_CONFIG)

export const { assertExpectedElementQueries, assertUnexpectedElementQueries } = createXmlAssertions(
	{
		namespaces: __DIALECTE_NAME___DIALECTE_CONFIG.namespaces,
	},
)
