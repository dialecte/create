/**
 * `node scripts/derive-oracle/type-check.ts <folder>...`: the generated files and probes of every folder, judged in
 * one `tsc --strict` run. Prints the folders that do not type-check, as a JSON list.
 */
import { typeCheck } from './type-probes.ts'

process.stdout.write(JSON.stringify(typeCheck({ folders: process.argv.slice(2) })))
