/**
 * The type-level half of the oracle: per element (and per parent, where a child is declared there), a probe that
 * the generated attribute type accepts the required attributes alone, refuses an object missing one, and refuses an
 * attribute the element does not have. `@ts-expect-error` turns a refusal that does not happen into an error, so
 * one `tsc --strict` over the generated files and their probes judges them all.
 */
import { spawnSync } from 'node:child_process'
import { readdirSync } from 'node:fs'
import { dirname, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

import { attributeNames, declarationUnder } from './derive-oracle.ts'

import type { DeclarationData, DefinitionData, ElementData } from '../../src/derive/derive.types.ts'
import type { Compile, Compiled } from './type-probes.types.ts'

const CREATE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const TSC = join(CREATE_ROOT, 'node_modules', 'typescript', 'bin', 'tsc')
/** The strictest options a consumer may turn on, as the fixtures' type-check uses. */
const STRICTEST = [
	'--noEmit',
	'--strict',
	'--target',
	'ES2022',
	'--module',
	'ESNext',
	'--moduleResolution',
	'Bundler',
	'--noUnusedLocals',
	'--noUnusedParameters',
	'--exactOptionalPropertyTypes',
	'--noUncheckedIndexedAccess',
	'--noPropertyAccessFromIndexSignature',
]
/** A key no schema declares: what the unknown-attribute probe writes. */
const UNKNOWN = 'dialecte-probe-unknown'

/** `probes.ts` for a dialecte whose generated files sit beside it. */
export function typeProbesSource(params: { definition: DefinitionData }): string {
	const { definition } = params
	const tags = Object.keys(definition).sort()
	const probes = tags.flatMap((tag) => [
		{ target: `AttributesMap[${JSON.stringify(tag)}]`, content: definition[tag] },
		...(definition[tag]?.children.sequence ?? [])
			.filter((child) => child in definition)
			.map((child) => ({
				target: `AttributesByParent[${JSON.stringify(tag)}][${JSON.stringify(child)}]`,
				content: declarationUnder({ definition, parent: tag, child }),
			})),
	])
	// only the maps a probe reads: the per-parent one exists only where an element holds another
	const maps = ['AttributesByParent', 'AttributesMap'].filter((map) =>
		probes.some(({ target }) => target.startsWith(`${map}[`)),
	)
	const lines = [
		'// Type probes of the generated attribute types - written by the derive oracle, never committed',
		...(maps.length > 0 ? [`import type { ${maps.join(', ')} } from './types.generated'`] : []),
		'',
	]
	let index = 0
	for (const { target, content } of probes) {
		if (content === undefined) continue
		for (const probe of probesOf({ content })) {
			if (probe.refused) lines.push(`// @ts-expect-error ${probe.refused}`)
			lines.push(`export const probe${index++}: ${target} = ${literal(probe.attributes)}`)
		}
	}
	return `${lines.join('\n')}\n`
}

/**
 * The folders whose files and probes do not type-check, judged in as few `tsc --strict` runs as tsc can hold: a batch
 * it crashes on (out of memory, on large schemas) is split in halves until each folder is judged.
 */
export function typeCheck(params: { folders: readonly string[]; compile?: Compile }): string[] {
	const { folders, compile = compileWithTsc } = params
	if (folders.length === 0) return []
	const { outcome, output } = compile(folders)
	if (outcome === 'passed') return []
	if (outcome === 'crashed') {
		if (folders.length === 1) return [...folders]
		const half = Math.ceil(folders.length / 2)
		return [
			...typeCheck({ folders: folders.slice(0, half), compile }),
			...typeCheck({ folders: folders.slice(half), compile }),
		].sort()
	}
	// a folder by its whole name: `…/1` must not claim the errors of `…/10`
	const failing = folders.filter((folder) => output.includes(`${folder}${sep}`))
	// a diagnostic tsc does not place in a folder (an option, a global) fails them all
	return failing.length > 0 ? [...failing].sort() : [...folders].sort()
}

/** `tsc` with the heap large schemas need; a run it does not finish (a signal, an abort) is a crash. */
function compileWithTsc(folders: readonly string[]): Compiled {
	const files = folders.flatMap((folder) =>
		readdirSync(folder)
			.filter((file) => file.endsWith('.ts'))
			.map((file) => join(folder, file)),
	)
	const run = spawnSync('node', ['--max-old-space-size=4096', TSC, ...STRICTEST, ...files], {
		encoding: 'utf-8',
		maxBuffer: 256 * 1024 * 1024,
	})
	if (run.status === 0) return { outcome: 'passed', output: run.stdout }
	// tsc reports diagnostics with 1 or 2; anything else did not finish
	if (run.status === 1 || run.status === 2) return { outcome: 'failed', output: run.stdout }
	return { outcome: 'crashed', output: run.stdout ?? '' }
}

type Probe = { readonly attributes: Readonly<Record<string, string>>; readonly refused?: string }

/** Accepted: the required attributes alone. Refused: one of them missing; an attribute the element lacks. */
function probesOf(params: { content: ElementData | DeclarationData }): Probe[] {
	const { content } = params
	const required = Object.fromEntries(
		content.attributes.sequence
			.filter((name) => content.attributes.details[name]?.required === true)
			.map((name) => [name, content.attributes.details[name]?.fixed ?? '']),
	)
	const [first] = Object.keys(required)
	const { [first ?? '']: _missing, ...withoutFirst } = required
	// no unknown-attribute probe where it cannot hold: an attribute wildcard (the type is closed on purpose), or no
	// attribute at all - TypeScript's empty object type `{}` takes any object (an X3 item: refuse it at the write
	// parameter, where `keyof` is not read)
	const probesUnknown = !('any' in content.attributes) && attributeNames({ content }).length > 0
	return [
		{ attributes: required },
		...(first === undefined ? [] : [{ attributes: withoutFirst, refused: `${first} is required` }]),
		...(probesUnknown
			? [{ attributes: { ...required, [UNKNOWN]: '' }, refused: 'an attribute it does not have' }]
			: []),
	]
}

function literal(attributes: Readonly<Record<string, string>>): string {
	const entries = Object.entries(attributes).map(
		([name, value]) => `${JSON.stringify(name)}: ${JSON.stringify(value)}`,
	)
	return `{ ${entries.join(', ')} }`
}
