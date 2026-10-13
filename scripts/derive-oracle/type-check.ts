/**
 * `node scripts/derive-oracle/type-check.ts [--tsc] <folder>...`: the generated files and probes of every folder,
 * judged in one run of `tsgo` (`--tsc`: of `tsc`). Prints the folders that do not type-check, as a JSON list.
 */
import { compileWithTsc, compileWithTsgo, typeCheck } from './type-probes.ts'

const args = process.argv.slice(2)
const compile = args.includes('--tsc') ? compileWithTsc : compileWithTsgo
const folders = args.filter((arg) => arg !== '--tsc')
process.stdout.write(JSON.stringify(typeCheck({ folders, compile })))
