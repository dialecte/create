/**
 * `node scripts/derive-oracle/run-oracle.ts <generated.json> [--write <folder>]`: the oracle on what the emitter
 * writes for one generated definition (`{ definition, types }`, as the Python generator returns it). Prints the
 * disagreements as a JSON list of ids - `<fact>/<element>`, `<fact>/<parent>><element>` - the form
 * `known-exceptions.json` lists. With `--write`, the constants, the types and their probes go to `folder` too, beside
 * the definition the caller writes there, for one `type-check.ts` run over many folders.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import { checkEmitted, emittedFiles } from './check-emitted.ts'

const [file, flag, folder] = process.argv.slice(2)
if (file === undefined || (flag !== undefined && (flag !== '--write' || folder === undefined)))
	throw new Error('usage: run-oracle.ts <generated.json> [--write <folder>]')
const { definition, types } = JSON.parse(readFileSync(file, 'utf-8'))
const disagreements = await checkEmitted({ definition, types })
if (folder !== undefined) {
	for (const [name, text] of Object.entries(emittedFiles({ definition, types }) ?? {}))
		writeFileSync(join(folder, name), text)
}
process.stdout.write(
	JSON.stringify(
		disagreements.map(({ fact, element, parent }) =>
			parent === undefined ? `${fact}/${element}` : `${fact}/${parent}>${element}`,
		),
	),
)
