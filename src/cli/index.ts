import { basename, resolve } from 'node:path'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { runGenerator } from './pyodide-runner.js'
import { scaffoldDialecte, dialecteIdFromPackageName } from './scaffold.js'

export { runGenerator } from './pyodide-runner.js'
export { scaffoldDialecte } from './scaffold.js'

const DEFAULT_CORE_VERSION = '^0.2.19'
const DEFAULT_VERSION = 'v1'

interface ParsedArgs {
	_: string[]
	flags: Record<string, string | boolean>
}

function parseArgs(argv: string[]): ParsedArgs {
	const _: string[] = []
	const flags: Record<string, string | boolean> = {}

	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i]
		if (arg.startsWith('--')) {
			const key = arg.slice(2)
			const next = argv[i + 1]
			if (next === undefined || next.startsWith('--')) {
				flags[key] = true
			} else {
				flags[key] = next
				i++
			}
		} else {
			_.push(arg)
		}
	}

	return { _, flags }
}

function printHelp(): void {
	console.log(`@dialecte/create - scaffold and generate Dialecte SDKs from XSD

Usage:
  create-dialecte create <schema.xsd> [options]   Scaffold a new dialecte package
  create-dialecte generate [options]              Generate definition files only
  create-dialecte <schema.xsd>                    Shorthand for "create"

create options:
  --name <pkg>           npm package name (default: @dialecte/<schema basename>)
  --out <dir>            target directory (default: ./<dialecte id>)
  --version <vN>         version folder name (default: ${DEFAULT_VERSION})
  --namespace <uri>      default XML namespace URI (default: derived placeholder)
  --core-version <ver>   @dialecte/core version range (default: ${DEFAULT_CORE_VERSION})

generate options:
  --entry <schema.xsd>   entry XSD file (required)
  --out-dir <dir>        output directory for generated .ts files (required)

  -h, --help             show this help
`)
}

async function runGenerateCommand(flags: Record<string, string | boolean>): Promise<void> {
	const entry = typeof flags.entry === 'string' ? flags.entry : undefined
	const outDir = typeof flags['out-dir'] === 'string' ? flags['out-dir'] : undefined

	if (!entry || !outDir) {
		throw new Error('generate requires --entry <schema.xsd> and --out-dir <dir>')
	}
	if (!existsSync(resolve(entry))) {
		throw new Error(`XSD file not found: ${entry}`)
	}

	await runGenerator({ entry, outDir })
}

async function runCreateCommand(
	positionals: string[],
	flags: Record<string, string | boolean>,
): Promise<void> {
	const entry = positionals[0]
	if (!entry) {
		throw new Error('create requires a path to an XSD schema: create-dialecte create <schema.xsd>')
	}
	if (!existsSync(resolve(entry))) {
		throw new Error(`XSD file not found: ${entry}`)
	}

	const schemaBase = basename(entry).replace(/\.xsd$/i, '')
	const packageName =
		typeof flags.name === 'string' ? flags.name : `@dialecte/${schemaBase.toLowerCase()}`
	const dialecteId = dialecteIdFromPackageName(packageName)

	const version = typeof flags.version === 'string' ? flags.version : DEFAULT_VERSION
	const namespaceUri =
		typeof flags.namespace === 'string' ? flags.namespace : `urn:dialecte:${dialecteId}`
	const coreVersion =
		typeof flags['core-version'] === 'string' ? flags['core-version'] : DEFAULT_CORE_VERSION
	const targetDir =
		typeof flags.out === 'string' ? flags.out : positionals[1] ?? `./${dialecteId}`

	await scaffoldDialecte({
		entry,
		targetDir,
		packageName,
		version,
		namespaceUri,
		coreVersion,
	})

	if (typeof flags.namespace !== 'string') {
		console.log('')
		console.log(
			`Note: default namespace set to "${namespaceUri}". Update src/${version}/config/namespaces.ts if needed.`,
		)
	}
}

export async function main(argv: string[] = process.argv.slice(2)): Promise<void> {
	const { _, flags } = parseArgs(argv)

	if (flags.help || flags.h || (_.length === 0 && Object.keys(flags).length === 0)) {
		printHelp()
		return
	}

	const command = _[0]

	if (command === 'generate') {
		await runGenerateCommand(flags)
		return
	}

	if (command === 'create') {
		await runCreateCommand(_.slice(1), flags)
		return
	}

	// Shorthand: first positional is an XSD path -> create.
	if (command && command.toLowerCase().endsWith('.xsd')) {
		await runCreateCommand(_, flags)
		return
	}

	printHelp()
	throw new Error(`Unknown command: ${command ?? '(none)'}`)
}

// Auto-run only when invoked directly as the CLI (not when imported, e.g. by tests).
const invokedDirectly =
	process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (invokedDirectly) {
	main().catch((err) => {
		console.error(`Error: ${err instanceof Error ? err.message : String(err)}`)
		process.exit(1)
	})
}
