import { __DialecteName__ } from './config'
import { __DIALECTE_NAME___DIALECTE_CONFIG } from './config/dialecte.config'
import { __DIALECTE_NAME___EXTENSION_MODULES } from './extensions'

import { Project } from '@dialecte/core'

import type { StorageParam, ExtensionModules } from '@dialecte/core'

/**
 * Create a __DialecteName__ project with pre-configured config and extensions.
 * Call .open(name) to initialize the store and hydrate state.
 */
export function create__DialecteName__Project<
	CustomModules extends ExtensionModules = Record<never, never>,
>(params?: {
	storage?: StorageParam
	extensions?: CustomModules
	/** Development switches of the engine, e.g. `{ perf: true }` to collect timings. */
	dev?: { perf?: boolean }
}): __DialecteName__.Project<CustomModules> {
	const { storage = { type: 'local' }, extensions, dev } = params ?? {}

	return new Project({
		configs: { __dialecteId__: __DIALECTE_NAME___DIALECTE_CONFIG },
		defaultConfigKey: '__dialecteId__',
		storage,
		extensions: {
			base: __DIALECTE_NAME___EXTENSION_MODULES,
			custom: extensions,
		},
		dev,
	}) as __DialecteName__.Project<CustomModules>
}
