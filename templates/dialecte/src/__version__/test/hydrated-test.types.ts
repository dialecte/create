import type { Config } from '@/__version__/config/dialecte.config'
import type { __DIALECTE_NAME___EXTENSION_MODULES } from '@/__version__/extensions'
import type * as CoreTest from '@dialecte/core/test'

/** The types a table-driven test is written with, bound to this dialecte and its extensions. */
export namespace __DialecteName__Test {
	/** The extension modules every test project of this dialecte is opened with. */
	export type Modules = typeof __DIALECTE_NAME___EXTENSION_MODULES
	export type BaseTestCase = CoreTest.BaseTestCase
	export type BaseXmlTestCase = CoreTest.BaseXmlTestCase
	export type TestCases<GenericTestCase extends BaseTestCase = BaseXmlTestCase> = Record<
		string,
		GenericTestCase
	>
	export type ActParams<GenericTestCase extends BaseXmlTestCase> = CoreTest.ActParams<
		Config,
		GenericTestCase,
		Modules
	>
	export type ActResult = CoreTest.ActResult
}
