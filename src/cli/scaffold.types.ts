export interface ScaffoldOptions {
	/** Absolute path to the entry .xsd file used to generate definitions. */
	entry: string
	/** Target directory for the new dialecte package. */
	targetDir: string
	/** npm package name, e.g. "@dialecte/foo". */
	packageName: string
	/** Version folder name, e.g. "v1". */
	version: string
	/** Pinned @dialecte/core version. */
	coreVersion: string
	/** The element that starts a document, when more than one could. */
	root?: string
}

export interface Replacements {
	packageName: string
	dialecteId: string
	DialecteName: string
	DIALECTE_NAME: string
	version: string
	coreVersion: string
	/** The `generate` options a regeneration must repeat, `--root` included, as one string. */
	generateOptions: string
}
