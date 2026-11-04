/** The `@dialecte/core` range a scaffolded package depends on, unless `--core-version` sets another. */
export const DEFAULT_CORE_VERSION = '^0.8.0'

/** The schema version folder of a scaffolded package, unless `--version` sets another. */
export const DEFAULT_VERSION = 'v1'

/** The flags each command takes: any other is refused, never ignored. */
export const COMMAND_FLAGS = {
	create: ['name', 'out', 'version', 'core-version', 'root'],
	generate: ['entry', 'out-dir', 'root'],
} as const
