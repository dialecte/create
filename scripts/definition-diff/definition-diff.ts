/**
 * The semantic difference between two generated definitions, grouped by what it is about.
 *
 *   node scripts/definition-diff/definition-diff.ts <before.generated.ts> <after.generated.ts> [--json]
 *
 * Each file is read back by importing it (Node strips its types), so what is compared is the data a
 * consumer gets, not the text. The review artefact of every lot of the generator rebuild.
 */

import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { diffDefinitions } from './diff-definitions.ts'
import { formatReport } from './format-report.ts'

import type { DefinitionData } from './diff-definitions.types.ts'

async function main(): Promise<void> {
	const args = process.argv.slice(2)
	const asJson = args.includes('--json')
	const [beforePath, afterPath] = args.filter((arg) => !arg.startsWith('--'))
	if (beforePath === undefined || afterPath === undefined) {
		process.stderr.write(
			'usage: definition-diff <before.generated.ts> <after.generated.ts> [--json]\n',
		)
		process.exit(2)
	}

	const before = await readDefinition(beforePath)
	const after = await readDefinition(afterPath)
	const differences = diffDefinitions({ before, after })

	process.stdout.write(
		asJson ? `${JSON.stringify(differences, null, '\t')}\n` : formatReport({ differences }),
	)
	process.exit(differences.length === 0 ? 0 : 1)
}

/** A generated definition as the data a consumer imports. */
async function readDefinition(path: string): Promise<DefinitionData> {
	const module: { DEFINITION?: DefinitionData } = await import(pathToFileURL(resolve(path)).href)
	if (module.DEFINITION === undefined) throw new Error(`${path} exports no DEFINITION`)
	return module.DEFINITION
}

await main()
