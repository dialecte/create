import { existsSync } from 'node:fs'
import { readdir, mkdir, readFile, writeFile, rm } from 'node:fs/promises'
import { join, resolve } from 'node:path'

import { TEMPLATES_DIR } from './paths.js'
import { runGenerator } from './pyodide-runner.js'

export interface ScaffoldOptions {
	/** Absolute path to the entry .xsd file used to generate definitions. */
	entry: string
	/** Target directory for the new dialecte package. */
	targetDir: string
	/** npm package name, e.g. "@dialecte/foo". */
	packageName: string
	/** Version folder name, e.g. "v1". */
	version: string
	/** Default namespace URI for the dialecte root. */
	namespaceUri: string
	/** Pinned @dialecte/core version. */
	coreVersion: string
}

export interface Replacements {
	packageName: string
	dialecteId: string
	DialecteName: string
	DIALECTE_NAME: string
	version: string
	namespaceUri: string
	coreVersion: string
}

/** Derive a bare dialecte id (e.g. "foo") from a package name (e.g. "@dialecte/foo"). */
export function dialecteIdFromPackageName(packageName: string): string {
	const last = packageName.split('/').pop() ?? packageName
	return last.replace(/[^a-zA-Z0-9]+/g, '').toLowerCase()
}

export function buildReplacements(options: ScaffoldOptions): Replacements {
	const dialecteId = dialecteIdFromPackageName(options.packageName)
	const DialecteName = dialecteId.charAt(0).toUpperCase() + dialecteId.slice(1)
	const DIALECTE_NAME = dialecteId.toUpperCase()

	return {
		packageName: options.packageName,
		dialecteId,
		DialecteName,
		DIALECTE_NAME,
		version: options.version,
		namespaceUri: options.namespaceUri,
		coreVersion: options.coreVersion,
	}
}

function applyReplacements(text: string, r: Replacements): string {
	return text
		.replaceAll('__packageName__', r.packageName)
		.replaceAll('__DIALECTE_NAME__', r.DIALECTE_NAME)
		.replaceAll('__DialecteName__', r.DialecteName)
		.replaceAll('__dialecteId__', r.dialecteId)
		.replaceAll('__version__', r.version)
		.replaceAll('__namespaceUri__', r.namespaceUri)
		.replaceAll('__coreVersion__', r.coreVersion)
}

function applyPathReplacements(path: string, r: Replacements): string {
	// Only directory/file name placeholders are meaningful in paths.
	const replaced = path.replaceAll('__version__', r.version)
	// `_gitignore` is shipped to avoid the template's own ignore being applied; emit as `.gitignore`.
	return replaced.replace(/(^|\/)_gitignore$/, '$1.gitignore')
}

async function copyTemplateTree(srcDir: string, destDir: string, r: Replacements): Promise<void> {
	const entries = await readdir(srcDir, { withFileTypes: true })
	await mkdir(destDir, { recursive: true })

	for (const entry of entries) {
		const srcPath = join(srcDir, entry.name)
		const destName = applyPathReplacements(entry.name, r)
		const destPath = join(destDir, destName)

		if (entry.isDirectory()) {
			await copyTemplateTree(srcPath, destPath, r)
			continue
		}

		// `.gitkeep` markers exist only to keep empty dirs in git; skip emitting them.
		if (entry.name === '.gitkeep') continue

		const raw = await readFile(srcPath, 'utf8')
		await writeFile(destPath, applyReplacements(raw, r), 'utf8')
	}
}

/**
 * Scaffold a new dialecte package from the bundled template, then generate its
 * definition files from the provided XSD.
 */
export async function scaffoldDialecte(options: ScaffoldOptions): Promise<void> {
	const targetDir = resolve(options.targetDir)
	const templateRoot = join(TEMPLATES_DIR, 'dialecte')

	if (existsSync(targetDir)) {
		const remaining = await readdir(targetDir)
		if (remaining.length > 0) {
			throw new Error(`Target directory is not empty: ${targetDir}`)
		}
	}

	const replacements = buildReplacements(options)

	console.log(`Scaffolding ${options.packageName} -> ${targetDir}`)
	await copyTemplateTree(templateRoot, targetDir, replacements)

	const definitionDir = join(targetDir, 'src', options.version, 'definition')
	console.log(`Generating definitions from ${options.entry}`)
	await runGenerator({ entry: options.entry, outDir: definitionDir })

	// Remove the placeholder keep-file if it slipped through.
	await rm(join(definitionDir, '.gitkeep'), { force: true })

	console.log('')
	console.log('Done. Next steps:')
	console.log(`  cd ${options.targetDir}`)
	console.log('  npm install')
	console.log('  npm run build')
}
