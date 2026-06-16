import {
	CUSTOM_RECORD_ID_ATTRIBUTE,
	CUSTOM_RECORD_ID_ATTRIBUTE_NAME,
	XMLNS_XSI_NAMESPACE,
} from '@dialecte/core/helpers'
import {
	createTestProject,
	createTestRecordFactory,
	createXmlAssertions,
	createTestRunner,
	XMLNS_DEV_NAMESPACE,
} from '@dialecte/core/test'

import { __DIALECTE_NAME___DIALECTE_CONFIG } from '@/__version__/config'
import { __DIALECTE_NAME___EXTENSION_MODULES } from '@/__version__/extensions'

import type { Config } from '@/__version__/config/dialecte.config'

type __DialecteName__Modules = typeof __DIALECTE_NAME___EXTENSION_MODULES

export const XMLNS___DIALECTE_NAME___NAMESPACE = `xmlns="${__DIALECTE_NAME___DIALECTE_CONFIG.namespaces.default.uri}"`
export const ALL_XMLNS_NAMESPACES = `${XMLNS___DIALECTE_NAME___NAMESPACE} ${XMLNS_DEV_NAMESPACE} ${XMLNS_XSI_NAMESPACE}`
export { CUSTOM_RECORD_ID_ATTRIBUTE, CUSTOM_RECORD_ID_ATTRIBUTE_NAME }

const __DIALECTE_NAME___EXTENSIONS = { base: __DIALECTE_NAME___EXTENSION_MODULES }

export const run__DialecteName__TestCases = createTestRunner<Config, __DialecteName__Modules>({
	dialecteConfig: __DIALECTE_NAME___DIALECTE_CONFIG,
	extensions: __DIALECTE_NAME___EXTENSIONS,
})

export async function create__DialecteName__TestProject(params: {
	sourceXml: string
	targetXml?: string
}) {
	const { sourceXml, targetXml } = params

	return createTestProject<Config, __DialecteName__Modules>({
		sourceXml,
		targetXml,
		dialecteConfig: __DIALECTE_NAME___DIALECTE_CONFIG,
		extensions: __DIALECTE_NAME___EXTENSIONS,
	})
}

export const create__DialecteName__TestRecord: ReturnType<typeof createTestRecordFactory<Config>> =
	createTestRecordFactory<Config>(__DIALECTE_NAME___DIALECTE_CONFIG)

export const { assertExpectedElementQueries, assertUnexpectedElementQueries } = createXmlAssertions({
	namespaces: __DIALECTE_NAME___DIALECTE_CONFIG.namespaces,
})
