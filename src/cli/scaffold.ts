import { existsSync } from 'node:fs'
import { readdir, mkdir, readFile, writeFile, rm } from 'node:fs/promises'
import { join, resolve } from 'node:path'

import { tsKey } from '../derive/ts-syntax.ts'
import { writeExample } from './example.ts'
import { formatScaffold } from './format-output.ts'
import { TEMPLATES_DIR } from './paths.ts'
import { runGenerator } from './pyodide-runner.ts'
import { XSI_NAMESPACE_URI } from './scaffold.constants.ts'

import type { Replacements, ScaffoldOptions } from './scaffold.types.ts'

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
		coreVersion: options.coreVersion,
		generateOptions: options.root === undefined ? '' : ` --root ${options.root}`,
	}
}

/**
 * The config entries of the namespaces the definition prefixes, keyed by prefix: core stores an xsi:type value with
 * the prefix declared for its namespace, the generated types with the definition's - the package's test checks they
 * agree. The XSI namespace is declared already; a prefix the config uses as a key (`default`, `xsi`) takes a number.
 */
function namespaceEntries(namespaces: readonly { prefix: string; uri: string }[]): string {
	const keys = new Set(['default', 'xsi'])
	return namespaces
		.filter(({ uri }) => uri !== XSI_NAMESPACE_URI)
		.map(({ prefix, uri }) => {
			let key = prefix
			for (let suffix = 2; keys.has(key); suffix++) key = `${prefix}_${suffix}`
			keys.add(key)
			return `\t${tsKey(key)}: { uri: ${quoted(uri)}, prefix: ${quoted(prefix)} },\n`
		})
		.join('')
}

/** A value as a single-quoted TypeScript string. */
function quoted(value: string): string {
	return `'${escapeForSingleQuotedString(value)}'`
}

/** The namespace URI lands inside a single-quoted TypeScript string: it must not end it. */
function escapeForSingleQuotedString(value: string): string {
	return value.replaceAll('\\', '\\\\').replaceAll("'", "\\'")
}

function applyReplacements(text: string, r: Replacements): string {
	return text
		.replaceAll('__packageName__', r.packageName)
		.replaceAll('__DIALECTE_NAME__', r.DIALECTE_NAME)
		.replaceAll('__DialecteName__', r.DialecteName)
		.replaceAll('__dialecteId__', r.dialecteId)
		.replaceAll('__version__', r.version)
		.replaceAll('__coreVersion__', r.coreVersion)
		.replaceAll('__generateOptions__', r.generateOptions)
}

function applyPathReplacements(path: string, r: Replacements): string {
	// Only directory/file name placeholders are meaningful in paths.
	const replaced = path
		.replaceAll('__version__', r.version)
		.replaceAll('__dialecteId__', r.dialecteId)
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
export async function scaffoldDialecte(
	options: ScaffoldOptions,
): Promise<{ namespaceUri: string; rootElement: string }> {
	const targetDir = resolve(options.targetDir)
	const templateRoot = join(TEMPLATES_DIR, 'dialecte')

	const existedBefore = existsSync(targetDir)
	if (existedBefore) {
		const remaining = await readdir(targetDir)
		if (remaining.length > 0) {
			throw new Error(`Target directory is not empty: ${targetDir}`)
		}
	}

	const replacements = buildReplacements(options)

	console.log(`Scaffolding ${options.packageName} -> ${targetDir}`)
	let namespaceUri = ''
	let rootElement = ''
	try {
		await copyTemplateTree(templateRoot, targetDir, replacements)

		const definitionDir = join(targetDir, 'src', options.version, 'definition')
		console.log(`Generating definitions from ${options.entry}`)
		const facts = await runGenerator({
			entry: options.entry,
			outDir: definitionDir,
			root: options.root,
		})

		// Remove the placeholder keep-file if it slipped through.
		await rm(join(definitionDir, '.gitkeep'), { force: true })

		// Documents live in the namespace of their root element - not necessarily the entry schema's
		// targetNamespace: an extension schema (IEC 61850-6-100 over SCL) has its own.
		namespaceUri = facts.example.root.namespaceUri
		rootElement = facts.example.root.name
		const namespacesFile = join(targetDir, 'src', options.version, 'config', 'namespaces.ts')
		const namespaces = await readFile(namespacesFile, 'utf8')
		await writeFile(
			namespacesFile,
			namespaces
				.replaceAll('__namespaceUri__', escapeForSingleQuotedString(namespaceUri))
				.replace('\t// __prefixedNamespaces__\n', namespaceEntries(facts.namespaces)),
			'utf8',
		)

		// the example names real elements: they are known now that the schema has been read
		await writeExample({
			exampleDir: join(targetDir, 'src', options.version, 'extensions', 'hello-world'),
			otherFiles: [
				join(targetDir, 'README.md'),
				join(targetDir, 'skills', `dialecte-${replacements.dialecteId}`, 'SKILL.md'),
				join(targetDir, 'skills', `dialecte-${replacements.dialecteId}`, 'references', 'api.md'),
			],
			facts: facts.example,
			defaultNamespaceUri: namespaceUri,
		})

		// names of any length are substituted into the template, so its line breaks cannot be right for all:
		// the package's own formatter configuration decides
		formatScaffold({ targetDir })
	} catch (error) {
		// A half-written package would only make the next attempt fail on a non-empty directory.
		await rm(targetDir, { recursive: true, force: true })
		if (existedBefore) await mkdir(targetDir)
		throw error
	}

	console.log('')
	console.log('Done. Next steps:')
	console.log(`  cd ${options.targetDir}`)
	// husky, run by the install, points git at the package's hooks only in a repository
	console.log('  git init')
	console.log('  npm install')
	console.log('  git add --all && git commit -m "scaffold"')
	console.log('')
	console.log(
		'The first install writes the skill API index and the type-bench baseline: commit them with the',
	)
	console.log('package. Then `npx dialecte gate --full` and `npx dialecte contrib` pass.')
	return { namespaceUri, rootElement }
}
