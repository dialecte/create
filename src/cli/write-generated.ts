import { mkdir, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'

import { deriveRoot } from '../derive/derive-root.ts'
import { emitConstantsSource } from '../derive/emit-constants.ts'
import { emitTypesSource } from '../derive/emit-types.ts'
import { exampleFacts } from '../derive/example-facts.ts'
import { formatGeneratedFiles } from './format-output.ts'

import type { ExampleFacts } from '../derive/derive.types.ts'
import type { GeneratedDefinition } from './write-generated.types.ts'

export const GENERATED_FILES = [
	'definition.generated.ts',
	'constants.generated.ts',
	'types.generated.ts',
] as const

/**
 * Write the three generated files of a definition - the definition the engine wrote, the constants and types
 * derived from it - formatted, and return the facts the scaffold's worked example names. The root is decided
 * first: a schema whose root is not decided leaves the folder as it was, never a new definition beside old tables.
 */
export async function writeGenerated(params: {
	outDir: string
	generated: GeneratedDefinition
	/** The element that starts a document, when more than one could. */
	root?: string
}): Promise<ExampleFacts> {
	const { outDir, generated, root } = params
	const { definition, types, source } = generated
	const rootElement = rootOf({ definition, chosen: root })

	const outAbs = resolve(outDir)
	await mkdir(outAbs, { recursive: true })
	const files: Record<(typeof GENERATED_FILES)[number], string> = {
		'definition.generated.ts': source,
		'constants.generated.ts': emitConstantsSource({ definition, root: rootElement, types }),
		'types.generated.ts': emitTypesSource({ definition }),
	}
	for (const [file, text] of Object.entries(files)) await writeFile(join(outAbs, file), text)
	formatGeneratedFiles({ outDir: outAbs, files: [...GENERATED_FILES] })
	return exampleFacts({ definition, root: rootElement })
}

/** The root of a document, the choice among several left to the `--root` flag. */
function rootOf(params: {
	definition: GeneratedDefinition['definition']
	chosen: string | undefined
}): string {
	try {
		return deriveRoot(params)
	} catch (error) {
		throw new Error(
			`${error instanceof Error ? error.message : String(error)} - pass --root <element>`,
		)
	}
}
