/**
 * Proof that the constants and types are a function of the definition: for each dialecte next to this
 * repo, derive `constants.generated.ts` and `types.generated.ts` from its committed definition, format
 * them with that package's oxfmt config, and compare them with the committed files.
 *
 *   node scripts/derive-check/derive-check.ts [dialecte ...]
 *
 * Local only: it reads the sibling repositories (core, scl, nsd, plc), beside create or in $DIALECTE_ROOT.
 * Exit 1 on any difference.
 */
import { spawnSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { deriveRoot } from '../../src/derive/derive-root.ts'
import { emitConstantsSource } from '../../src/derive/emit-constants.ts'
import { emitTypesSource } from '../../src/derive/emit-types.ts'

import type { DefinitionData } from '../../src/derive/derive.types.ts'
import type { DialecteLocation, ProofRoot } from './derive-check.types.ts'

const CREATE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
// the folder holding the sibling repositories; DIALECTE_ROOT overrides it (a worktree of create lives elsewhere)
const DIALECTE_ROOT = resolve(process.env.DIALECTE_ROOT ?? resolve(CREATE_ROOT, '..'))

/** Each dialecte: its package root and the folder of its generated definition. */
const DIALECTES: Readonly<Record<string, DialecteLocation>> = {
	'core-test': { packageRoot: 'core', folder: 'src/test/generated' },
	scl: { packageRoot: 'scl', folder: 'src/v2019C1/definition' },
	nsd: { packageRoot: 'nsd', folder: 'src/v2017A/definition' },
	'plc-v1': { packageRoot: 'plc', folder: 'src/v1/definition' },
	'plc-tc6': { packageRoot: 'plc', folder: 'src/tc6-v201/definition' },
}

async function main(): Promise<void> {
	const requested = process.argv.slice(2)
	const names = requested.length > 0 ? requested : Object.keys(DIALECTES)
	let differing = 0
	for (const name of names) {
		const dialecte = DIALECTES[name]
		if (dialecte === undefined) throw new Error(`unknown dialecte ${name}`)
		const folder = join(DIALECTE_ROOT, dialecte.packageRoot, dialecte.folder)
		if (!existsSync(folder)) {
			process.stdout.write(`${name}: skipped (${folder} absent)\n`)
			continue
		}
		// TYPES: the types an instance may name with xsi:type; a definition without it predates the rebuilt generator
		const { DEFINITION, TYPES } = await import(
			pathToFileURL(join(folder, 'definition.generated.ts')).href
		)
		if (TYPES === undefined) {
			throw new Error(
				`${name}: its definition exports no TYPES - regenerate it with @dialecte/create`,
			)
		}
		const { ROOT_ELEMENT } = await import(
			pathToFileURL(join(folder, 'constants.generated.ts')).href
		)
		const root = rootOf({ definition: DEFINITION, committed: ROOT_ELEMENT })
		process.stdout.write(`${name} root: ${root.note}\n`)
		const derived = {
			'constants.generated.ts': emitConstantsSource({
				definition: DEFINITION,
				root: root.tag,
				types: TYPES,
			}),
			'types.generated.ts': emitTypesSource({ definition: DEFINITION }),
		}
		const formatted = format({
			packageRoot: join(DIALECTE_ROOT, dialecte.packageRoot),
			files: derived,
		})
		for (const [file, text] of Object.entries(formatted)) {
			const committed = readFileSync(join(folder, file), 'utf-8')
			const same = committed === text
			if (!same) differing++
			process.stdout.write(
				`${name} ${file}: ${same ? 'identical' : firstDifference({ committed, derived: text })}\n`,
			)
		}
	}
	process.exit(differing === 0 ? 0 : 1)
}

/**
 * The root derived from the definition alone; when several elements can start a document, the
 * committed root is taken as the choice the schema author made (and must be one of them).
 */
function rootOf(params: { definition: DefinitionData; committed: string }): ProofRoot {
	const { definition, committed } = params
	try {
		const tag = deriveRoot({ definition })
		return {
			tag,
			note:
				tag === committed ? `${tag}, derived` : `${tag}, derived, but ${committed} is committed`,
		}
	} catch {
		const tag = deriveRoot({ definition, chosen: committed })
		return { tag, note: `${tag}, chosen among several candidates` }
	}
}

/** The files formatted the way the package formats its own: its oxfmt config, in a scratch folder. */
function format(params: {
	packageRoot: string
	files: Readonly<Record<string, string>>
}): Record<string, string> {
	const { packageRoot, files } = params
	const scratch = mkdtempSync(join(tmpdir(), 'derive-check-'))
	try {
		return formatIn({ scratch, packageRoot, files })
	} finally {
		rmSync(scratch, { recursive: true, force: true })
	}
}

function formatIn(params: {
	scratch: string
	packageRoot: string
	files: Readonly<Record<string, string>>
}): Record<string, string> {
	const { scratch, packageRoot, files } = params
	for (const config of ['.oxfmtrc.json', '.oxfmtrc.jsonc']) {
		if (existsSync(join(packageRoot, config)))
			copyFileSync(join(packageRoot, config), join(scratch, config))
	}
	for (const [file, text] of Object.entries(files)) writeFileSync(join(scratch, file), text)
	// the package's own formatter version: a layout change of one oxfmt release is not a difference
	const ownOxfmt = join(packageRoot, 'node_modules', '.bin', 'oxfmt')
	const oxfmt = existsSync(ownOxfmt) ? ownOxfmt : join(CREATE_ROOT, 'node_modules', '.bin', 'oxfmt')
	const run = spawnSync(oxfmt, Object.keys(files), { cwd: scratch, encoding: 'utf-8' })
	if (run.status !== 0) throw new Error(`oxfmt failed: ${run.stderr}`)
	return Object.fromEntries(
		Object.keys(files).map((file) => [file, readFileSync(join(scratch, file), 'utf-8')]),
	)
}

function firstDifference(params: { committed: string; derived: string }): string {
	const committedLines = params.committed.split('\n')
	const derivedLines = params.derived.split('\n')
	const index = committedLines.findIndex((line, position) => line !== derivedLines[position])
	const at = index === -1 ? Math.min(committedLines.length, derivedLines.length) : index
	return `differs at line ${at + 1}\n    committed: ${committedLines[at] ?? '(end)'}\n    derived:   ${derivedLines[at] ?? '(end)'}`
}

await main()
