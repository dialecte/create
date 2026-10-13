import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

import { emitConstantsSource } from '../../src/derive/emit-constants.ts'
import { emitTypesSource } from '../../src/derive/emit-types.ts'
import { checkDerivation } from './derive-oracle.ts'
import { typeProbesSource } from './type-probes.ts'

import type { DefinitionData, TypesData } from '../../src/derive/derive.types.ts'
import type { Disagreement, EmittedConstants } from './derive-oracle.types.ts'

/**
 * The constants the emitter writes for a definition, loaded as a module and judged by the oracle - what the corpus
 * and fuzz tiers run on every schema. The root is the first element nothing else holds, else the first global one;
 * a definition with elements but neither cannot be written (the CLI refuses it), which is reported as a root
 * disagreement. A definition without elements (a schema of types only) has nothing to write or judge.
 */
export async function checkEmitted(params: {
	definition: DefinitionData
	types: TypesData
}): Promise<Disagreement[]> {
	const { definition, types } = params
	// a schema of types or attributes only: no document, no file to write
	if (Object.keys(definition).length === 0) return []
	const root = firstRoot({ definition })
	if (root === undefined) return [{ fact: 'root', element: '*', expected: [], emitted: undefined }]
	const constants = await loaded({ source: emitConstantsSource({ definition, root, types }) })
	return checkDerivation({ definition, types, constants })
}

/**
 * The files the emitter writes beside a definition, and their type probes, by file name; `undefined` when no
 * element can start a document.
 */
export function emittedFiles(params: {
	definition: DefinitionData
	types: TypesData
}): Record<string, string> | undefined {
	const { definition, types } = params
	const root = firstRoot({ definition })
	if (root === undefined) return undefined
	return {
		'constants.generated.ts': emitConstantsSource({ definition, root, types }),
		'types.generated.ts': emitTypesSource({ definition, types, root }),
		'probes.ts': typeProbesSource({ definition, types, root }),
	}
}

/**
 * The root the files are written for: the first element nothing else holds, else - every one held by another - the
 * first global element, as `--root` would choose it.
 */
function firstRoot(params: { definition: DefinitionData }): string | undefined {
	const { definition } = params
	const tags = Object.keys(definition).sort()
	return (
		tags.find((tag) => (definition[tag]?.parents ?? []).every((parent) => parent === tag)) ??
		tags.find((tag) => definition[tag]?.global === true)
	)
}

/** A `constants.generated.ts` source as values: written to a scratch folder and imported (its type imports erase). */
async function loaded(params: { source: string }): Promise<EmittedConstants> {
	const scratch = mkdtempSync(join(tmpdir(), 'derive-oracle-'))
	try {
		const file = join(scratch, 'constants.generated.ts')
		writeFileSync(file, params.source)
		return (await import(pathToFileURL(file).href)) as EmittedConstants
	} finally {
		rmSync(scratch, { recursive: true, force: true })
	}
}
