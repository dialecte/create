import { readdir, readFile, rename, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

import type { ExampleFacts } from './pyodide-runner.js'

// Lines between these markers exist only when the root allows a child; both lines are dropped.
const IF_CHILD = '__ifExampleChild__'
const END_IF_CHILD = '__endIfExampleChild__'

/**
 * Write the worked example with the names of the schema it was generated from, so a reader opens
 * real elements instead of lookups. Runs after generation, which is when those names are known.
 * A root that allows no child keeps the read and loses the write: there is nothing to ensure.
 */
export async function writeExample(params: {
	/** The example's folder in the new package. */
	exampleDir: string
	/** Other files of the package that show the example (the readme). */
	otherFiles: string[]
	facts: ExampleFacts
	/** The package's default namespace: its elements are `default:` in an XPath step. */
	defaultNamespaceUri: string
}): Promise<void> {
	const { exampleDir, otherFiles, facts, defaultNamespaceUri } = params
	const replacements = buildExampleReplacements({ facts, defaultNamespaceUri })

	if (facts.child === null) await rm(join(exampleDir, 'transaction'), { recursive: true })

	const entries = await readdir(exampleDir, { recursive: true, withFileTypes: true })
	const files = entries
		.filter((entry) => entry.isFile())
		.map((entry) => join(entry.parentPath, entry.name))
	for (const file of [...files, ...otherFiles]) {
		const raw = await readFile(file, 'utf8')
		const kept = keepConditionalBlocks({ text: raw, hasChild: facts.child !== null })
		await writeFile(file, replaceAll({ text: kept, replacements }), 'utf8')
		const renamed = replaceAll({ text: file, replacements })
		if (renamed !== file) await rename(file, renamed)
	}
}

function buildExampleReplacements(params: {
	facts: ExampleFacts
	defaultNamespaceUri: string
}): Record<string, string> {
	const { facts, defaultNamespaceUri } = params
	const { root, child } = facts
	const rootStep = xpathStep({ ...root, defaultNamespaceUri })
	const replacements: Record<string, string> = {
		__exampleRootKey__: tsKey(root.name),
		__exampleRootXPath__: tsStringContent(`/${rootStep}`),
		__exampleRoot__: root.name,
	}
	if (child === null) return replacements

	const attributes = child.requiredAttributes
	const predicates = attributes.map(({ name, value }) => `[@${name}=${xpathLiteral(value)}]`)
	return {
		...replacements,
		__exampleChildKey__: tsKey(child.name),
		__exampleChildXPath__: tsStringContent(
			`/${rootStep}/${xpathStep({ ...child, defaultNamespaceUri })}${predicates.join('')}`,
		),
		// a comment in the template, so the template itself stays valid TypeScript
		' /* __exampleChildAttributesArgument__ */':
			attributes.length === 0
				? ''
				: `, attributes: { ${attributes.map(({ name, value }) => `${tsKey(name)}: '${tsStringContent(value)}'`).join(', ')} }`,
		__exampleChildAttributesXml__: attributes
			.map(({ name, value }) => ` ${name}="${xmlAttributeInTemplateLiteral(value)}"`)
			.join(''),
		__ExampleChild__: pascalCase(child.name),
		'__example-child__': kebabCase(child.name),
		__exampleChild__: child.name,
	}
}

function keepConditionalBlocks(params: { text: string; hasChild: boolean }): string {
	const { text, hasChild } = params
	const kept: string[] = []
	let inBlock = false
	for (const line of text.split('\n')) {
		if (line.includes(IF_CHILD)) inBlock = true
		else if (line.includes(END_IF_CHILD)) inBlock = false
		else if (!inBlock || hasChild) kept.push(line)
	}
	return kept.join('\n')
}

function replaceAll(params: { text: string; replacements: Record<string, string> }): string {
	return Object.entries(params.replacements).reduce(
		(text, [placeholder, value]) => text.replaceAll(placeholder, value),
		params.text,
	)
}

/** An element step: bare without a namespace, `default:` in the package's, by local name otherwise. */
function xpathStep(params: { name: string; namespaceUri: string; defaultNamespaceUri: string }) {
	const { name, namespaceUri, defaultNamespaceUri } = params
	if (namespaceUri === '') return name
	if (namespaceUri === defaultNamespaceUri) return `default:${name}`
	return `*[local-name()="${name}"]`
}

function xpathLiteral(value: string): string {
	if (!value.includes('"')) return `"${value}"`
	if (!value.includes("'")) return `'${value}'`
	return `concat("${value.replaceAll('"', `", '"', "`)}")`
}

/** A key of an object literal: bare when it is an identifier, quoted otherwise (`'root-element'`). */
function tsKey(name: string): string {
	return /^[A-Za-z_$][\w$]*$/.test(name) ? name : `'${name}'`
}

/** Text that lands inside a single-quoted TypeScript string. */
function tsStringContent(value: string): string {
	return value.replaceAll('\\', '\\\\').replaceAll("'", "\\'")
}

/** An XML attribute value inside a TypeScript template literal. */
function xmlAttributeInTemplateLiteral(value: string): string {
	return value
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('"', '&quot;')
		.replaceAll('\\', '\\\\')
		.replaceAll('`', '\\`')
		.replaceAll('${', '\\${')
}

/** `child-element` → `ChildElement`, `uid.pre` → `UidPre`: the method is `ensure<PascalCase>`. */
function pascalCase(name: string): string {
	return name
		.split(/[^A-Za-z0-9]+/)
		.filter(Boolean)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join('')
}

/** `ConnectedAP` → `connected-ap`, `uid.pre` → `uid-pre`: the file is `ensure-<kebab-case>.ts`. */
function kebabCase(name: string): string {
	return name
		.replace(/([a-z0-9])([A-Z])/g, '$1-$2')
		.replace(/[^A-Za-z0-9]+/g, '-')
		.replace(/^-|-$/g, '')
		.toLowerCase()
}
