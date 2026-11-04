import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, resolve } from 'node:path'

import { OXFMT_BIN, OXFMT_CONFIGS } from './format-output.constants.ts'
import { PACKAGE_ROOT } from './paths.ts'

/** The directories from the output directory up to the root. */
function* ancestors(outDir: string): Generator<string> {
	let directory = resolve(outDir)
	while (true) {
		yield directory
		const parent = dirname(directory)
		if (parent === directory) return
		directory = parent
	}
}

/**
 * The formatter of the project the files are generated into: its configuration says how, and its
 * own oxfmt when installed says with which version, so a regeneration is byte for byte what the
 * project committed. Without a project configuration there is nothing to match, and the emitter's
 * own style is kept rather than the defaults of a formatter nobody configured.
 */
function findFormatter(outDir: string): string | undefined {
	const hasConfig = [...ancestors(outDir)].some((directory) =>
		OXFMT_CONFIGS.some((config) => existsSync(join(directory, config))),
	)
	if (!hasConfig) return undefined

	for (const directory of ancestors(outDir)) {
		const candidate = join(directory, OXFMT_BIN)
		if (existsSync(candidate)) return candidate
	}
	return bundledFormatter()
}

/**
 * create's own oxfmt, wherever npm put it: under create's folder, or hoisted beside it as `npm create` and npx
 * install it. Resolved the way Node resolves an import, never from a fixed path.
 */
function bundledFormatter(): string | undefined {
	try {
		const manifestPath = createRequire(join(PACKAGE_ROOT, 'package.json')).resolve(
			'oxfmt/package.json',
		)
		const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as { bin: { oxfmt: string } }
		return join(dirname(manifestPath), manifest.bin.oxfmt)
	} catch {
		return undefined
	}
}

/**
 * Format a new package in place with create's own oxfmt (the template's version) and the package's formatter
 * configuration. Never fatal: when no formatter runs, say how to format it by hand.
 */
export function formatScaffold(params: { targetDir: string }): void {
	const formatter = bundledFormatter()
	const result =
		formatter === undefined
			? undefined
			: spawnSync(process.execPath, [formatter, '.'], {
					cwd: resolve(params.targetDir),
					stdio: 'pipe',
				})
	if (result?.status === 0) return
	console.warn(
		'Warning: could not format the package: run `npm run format:fix` after `npm install`.',
	)
}

/**
 * Format the generated files in place. The emitter writes them close to the house style already;
 * this makes them byte for byte what the formatter of the project would produce, so a regeneration
 * shows only what changed in the schema. Never fatal: the files are correct either way.
 */
export function formatGeneratedFiles(params: { outDir: string; files: string[] }): void {
	const { outDir, files } = params
	const formatter = findFormatter(outDir)
	if (formatter === undefined) return

	// oxfmt looks its configuration up from the working directory
	const result = spawnSync(formatter, files, { cwd: resolve(outDir), stdio: 'pipe' })
	if (result.status === 0) return

	// a project that ignores generated files in its formatter configuration has made a choice
	const stderr = String(result.stderr ?? '')
	if (stderr.includes('excluded by ignore rules')) return

	console.warn(
		`Warning: could not format the generated files (${formatter} exited ${result.status}).`,
	)
}
