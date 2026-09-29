/**
 * CLI smoke test: run the WASM generator against a minimal fixture XSD and
 * assert the three definition files are produced. Exercises the full Pyodide
 * pipeline offline. Exits non-zero on failure.
 *
 * Usage: node scripts/smoke.mjs   (run after `npm run build` and `npm run vendor`)
 *
 * SMOKE_INSTALL=1 also installs a scaffolded package and type-checks it (network, slower): the
 * only check that catches a generator ahead of the published engine. DIALECTE_CORE=<core dir or
 * .tgz> installs that engine instead of the default range, to test against an unreleased core.
 */
import { spawnSync } from 'node:child_process'
import { mkdtemp, readdir, rm, stat, readFile, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

import { main as runCli, runGenerator } from '../dist/cli/index.js'

const FIXTURE = new URL('../test/fixtures/minimal.xsd', import.meta.url).pathname
const NO_NAMESPACE_FIXTURE = new URL('../test/fixtures/no-namespace.xsd', import.meta.url).pathname
const COMMENTED_FIXTURE = new URL('../test/fixtures/commented-namespace.xsd', import.meta.url)
	.pathname
const TWO_ROOTS_FIXTURE = new URL('../test/fixtures/two-roots.xsd', import.meta.url).pathname
const EXTENSION_FIXTURE = new URL('../test/fixtures/extension/entry.xsd', import.meta.url).pathname
const EXPECTED = ['definition.generated.ts', 'constants.generated.ts', 'types.generated.ts']

/** Scaffold a package and check what a consumer relies on in the files it gets. */
async function assertScaffold({ fixture, packageName, expectations, options = [] }) {
	const targetDir = await mkdtemp(join(tmpdir(), 'dialecte-scaffold-'))
	try {
		await runCli(['create', fixture, '--name', packageName, '--out', targetDir, ...options])
		for (const { file, includes, excludes, absent, reason } of expectations) {
			const path = join(targetDir, file)
			const exists = await stat(path).then(
				() => true,
				() => false,
			)
			if (absent) {
				if (exists) throw new Error(`${file} of ${packageName}: ${reason} (expected no such file)`)
				continue
			}
			const content = await readFile(path, 'utf8')
			if (includes !== undefined && !content.includes(includes)) {
				throw new Error(
					`${file} of ${packageName}: ${reason} (expected to find ${JSON.stringify(includes)})`,
				)
			}
			if (excludes !== undefined && content.includes(excludes)) {
				throw new Error(
					`${file} of ${packageName}: ${reason} (expected NOT to find ${JSON.stringify(excludes)})`,
				)
			}
		}
		await assertNoExamplePlaceholderLeft({ targetDir, packageName })
	} finally {
		await rm(targetDir, { recursive: true, force: true })
	}
}

/** Every example placeholder is filled from the schema: none may reach the package. */
async function assertNoExamplePlaceholderLeft({ targetDir, packageName }) {
	const entries = await readdir(targetDir, { recursive: true, withFileTypes: true })
	for (const entry of entries) {
		const path = join(entry.parentPath, entry.name)
		if (path.includes('/node_modules/')) continue
		if (/__example|__Example|__if|__endIf/i.test(entry.name)) {
			throw new Error(`${packageName}: a placeholder is left in the file name ${path}`)
		}
		if (!entry.isFile()) continue
		const content = await readFile(path, 'utf8')
		const left = content.match(
			/__example[A-Za-z-]*__|__Example[A-Za-z]*__|__(end)?[iI]fExample[A-Za-z]*__/,
		)
		if (left) throw new Error(`${packageName}: ${left[0]} is left in ${path}`)
	}
}

/** A scaffold that fails must not leave a half-written package the next attempt trips over. */
async function assertFailedScaffoldLeavesNothing() {
	const parent = await mkdtemp(join(tmpdir(), 'dialecte-failed-'))
	const brokenXsd = join(parent, 'broken.xsd')
	const targetDir = join(parent, 'pkg')
	try {
		await writeFile(brokenXsd, '<not-a-schema/>')
		let failed = false
		try {
			await runCli(['create', brokenXsd, '--name', '@acme/broken', '--out', targetDir])
		} catch {
			failed = true
		}
		if (!failed) throw new Error('scaffolding a broken schema should fail')
		const left = await stat(targetDir).then(
			() => true,
			() => false,
		)
		if (left) throw new Error(`a failed scaffold left ${targetDir} behind`)

		// the interpreter is shared: a failed run must release its mounts for the next one
		await runGenerator({ entry: FIXTURE, outDir: join(parent, 'after'), quiet: true })
		console.log('A failed scaffold leaves nothing behind, and the next run works.')
	} finally {
		await rm(parent, { recursive: true, force: true })
	}
}

/**
 * npm runs a bin through a symlink (`node_modules/.bin/create-dialecte`), and so do `npm create` and
 * `npx`. The CLI must start when invoked that way, not only when its file is run directly.
 */
async function assertRunsThroughABinLink() {
	const dir = await mkdtemp(join(tmpdir(), 'dialecte-bin-'))
	try {
		const link = join(dir, 'create-dialecte')
		await symlink(new URL('../dist/cli/index.js', import.meta.url).pathname, link)
		const result = spawnSync(process.execPath, [link, '--version'], { encoding: 'utf8' })
		if (!/^\d+\.\d+\.\d+/.test(result.stdout.trim())) {
			throw new Error(
				`run through a bin link, the CLI printed ${JSON.stringify(result.stdout.trim())} instead of its version: npm create / npx would do nothing`,
			)
		}
		console.log('The CLI runs through a bin link, as npm create and npx invoke it.')
	} finally {
		await rm(dir, { recursive: true, force: true })
	}
}

/** `-h` and `--version` are advertised: they must answer, not fail as unknown commands. */
async function assertHelpAndVersion() {
	const printed = []
	const original = console.log
	console.log = (line) => printed.push(String(line))
	try {
		await runCli(['-h'])
		await runCli(['--version'])
	} finally {
		console.log = original
	}
	if (!printed.some((line) => line.includes('Usage:'))) throw new Error('-h did not print the help')
	if (!printed.some((line) => /^\d+\.\d+\.\d+/.test(line))) {
		throw new Error('--version did not print the version')
	}
	console.log('-h and --version answer.')
}

function run(command, args, cwd) {
	const result = spawnSync(command, args, { cwd, encoding: 'utf8', stdio: 'pipe' })
	if (result.status !== 0) {
		throw new Error(
			`${command} ${args.join(' ')} failed in ${cwd}:\n${result.stdout}\n${result.stderr}`,
		)
	}
	return result.stdout
}

/** The engine to install: a tarball as given, or one packed from a core checkout. */
function coreTarball(core, packDir) {
	if (core.endsWith('.tgz')) return resolve(core)
	const [packed] = JSON.parse(run('npm', ['pack', '--json', '--pack-destination', packDir], core))
	return join(packDir, packed.filename)
}

/** A scaffolded package must install and compile against the engine it targets. */
async function assertInstalledScaffoldTypeChecks() {
	if (process.env.SMOKE_INSTALL !== '1') {
		console.log('Install check skipped (SMOKE_INSTALL=1 to run it).')
		return
	}
	const parent = await mkdtemp(join(tmpdir(), 'dialecte-install-'))
	const targetDir = join(parent, 'pkg')
	try {
		await runCli(['create', FIXTURE, '--name', '@acme/installed', '--out', targetDir])

		const core = process.env.DIALECTE_CORE
		if (core !== undefined && core !== '') {
			const manifestPath = join(targetDir, 'package.json')
			const manifest = JSON.parse(await readFile(manifestPath, 'utf8'))
			manifest.dependencies['@dialecte/core'] = `file:${coreTarball(resolve(core), parent)}`
			await writeFile(manifestPath, JSON.stringify(manifest, null, '\t'))
		}

		run('npm', ['install', '--no-audit', '--no-fund'], targetDir)
		run('npm', ['run', 'type-check'], targetDir)
		run('npm', ['run', 'type-check:test'], targetDir)
		console.log(`Installed scaffold type-checks (engine: ${core || 'default range'}).`)
	} finally {
		await rm(parent, { recursive: true, force: true })
	}
}

async function main() {
	const outDir = await mkdtemp(join(tmpdir(), 'dialecte-smoke-'))
	try {
		await runGenerator({ entry: FIXTURE, outDir, quiet: true })

		for (const file of EXPECTED) {
			const path = join(outDir, file)
			const info = await stat(path)
			if (!info.isFile() || info.size === 0) {
				throw new Error(`Missing or empty output: ${file}`)
			}
		}

		const constants = await readFile(join(outDir, 'constants.generated.ts'), 'utf8')
		if (!constants.includes('Root') || !constants.includes('Item')) {
			throw new Error('Generated constants missing expected element names')
		}

		console.log('Smoke test passed: 3 files generated with expected elements.')

		await assertScaffold({
			fixture: FIXTURE,
			packageName: '@acme/widget',
			expectations: [
				{
					file: 'package.json',
					includes: '"@dialecte/core": "^0.5.',
					reason: 'the engine range must target the current release line',
				},
				{
					file: 'package.json',
					includes: '"type-check": "tsc -p tsconfig.build.json --noEmit"',
					reason: 'the root tsconfig only references the others, so checking it checks nothing',
				},
				{
					file: 'src/v1/config/namespaces.ts',
					includes: "uri: 'urn:dialecte:example'",
					reason: 'the default namespace must be the target namespace of the schema',
				},
				{
					file: 'src/v1/config/hydrated.types.ts',
					includes: 'Core.Project<Config, WidgetModules & GenericCustomModules>',
					reason: 'a project takes the raw extension modules, which it merges itself',
				},
				{
					file: 'src/v1/definition/constants.generated.ts',
					includes: '\tbyParent: {',
					reason: 'one ATTRIBUTES constant, by tag and as declared under each parent',
				},
				{
					file: 'src/v1/definition/types.generated.ts',
					includes: 'export type AttributesByParent = {',
					reason: 'the generated map the by-parent half is checked against',
				},
				{
					file: 'src/v1/test/assert-valid-xml.ts',
					includes: 'export const assertValidWidgetTestCases = assertValidXmlTestCases',
					reason: 'fixtures are checked against the schema, with the validator core provides',
				},
				{
					file: 'src/v1/test/hydrated-test.ts',
					includes: 'assertValidWidgetTestCases({ testCases: params.testCases })',
					reason: 'the runner checks every case before the suite runs',
				},
				{
					file: 'src/v1/extensions/index.ts',
					includes: 'WIDGET_EXTENSION_MODULES = { helloWorld }',
					reason: 'the hello-world example ships registered, so its tests run out of the box',
				},
				{
					file: 'src/v1/extensions/hello-world/query/say-hello.test.ts',
					includes: 'runWidgetTestCases.withoutExport',
					reason: 'the example tests are written with the runners of the package',
				},
				{
					file: 'src/v1/extensions/hello-world/query/say-hello.test.ts',
					includes: 'countByTagName: { Root: 1, Item: 1 }',
					reason: 'the example names the elements of the schema, so it reads plainly',
				},
				{
					file: 'src/v1/extensions/hello-world/transaction/ensure-item.test.ts',
					includes: 'runWidgetTestCases.withExport',
					reason: 'the write of the example is checked as XML, with the export runner',
				},
				{
					file: 'src/v1/extensions/hello-world/transaction/ensure-item.test.ts',
					includes: `'/default:Root/default:Item[@id="hello-world"]'`,
					reason: 'an element of the default namespace is prefixed, its required attribute matched',
				},
				{
					file: 'src/v1/extensions/hello-world/transaction/ensure-item.ts',
					includes: "tagName: 'Item', attributes: { id: 'hello-world' },",
					reason: 'the example writes with the typed API, the attribute the schema requires filled',
				},
				{
					file: 'src/v1/extensions/hello-world/transaction/index.ts',
					includes: "export { ensureItem } from './ensure-item'",
					reason: 'the method is named after the element it ensures',
				},
				{
					file: 'README.md',
					includes: 'tx.helloWorld.ensureItem()',
					reason: 'the readme shows the method the example actually has',
				},
			],
		})
		await assertScaffold({
			fixture: NO_NAMESPACE_FIXTURE,
			packageName: '@acme/plain',
			expectations: [
				{
					file: 'src/v1/config/namespaces.ts',
					includes: "uri: ''",
					reason: 'a schema without a target namespace must not get an invented one',
				},
				{
					file: 'src/v1/extensions/hello-world/transaction/ensure-child-element.test.ts',
					includes: `'/root-element/child-element[@id="hello-world"]'`,
					reason: 'an element of no namespace is a bare step',
				},
				{
					file: 'src/v1/extensions/hello-world/query/say-hello.test.ts',
					includes: "countByTagName: { 'root-element': 1, 'child-element': 1 }",
					reason: 'a name that is not an identifier is a quoted key',
				},
			],
		})
		await assertScaffold({
			fixture: FIXTURE,
			packageName: '@acme/dashed',
			options: ['--namespace', '-urn'],
			expectations: [
				{
					file: 'src/v1/config/namespaces.ts',
					includes: "uri: '-urn'",
					reason: 'a value starting with a dash is still the value of its flag',
				},
			],
		})
		await assertScaffold({
			fixture: COMMENTED_FIXTURE,
			packageName: '@acme/quoted',
			expectations: [
				{
					file: 'src/v1/config/namespaces.ts',
					includes: "uri: 'urn:it\\'s:real'",
					reason: 'the namespace is the one of the root tag, not of a comment, and it is escaped',
				},
				{
					file: 'src/v1/definition/types.generated.ts',
					// the formatter picks the quote that needs no escaping
					includes: `"don't" | 'plain'`,
					reason: 'an enumeration value holding a quote must still compile',
				},
				// this root allows no child: the example keeps its read and has no write to show
				{
					file: 'src/v1/extensions/hello-world/transaction',
					absent: true,
					reason: 'there is no child to ensure',
				},
				{
					file: 'src/v1/extensions/hello-world/index.ts',
					excludes: "from './transaction'",
					reason: 'the example registers no transaction module',
				},
				{
					file: 'src/v1/extensions/hello-world/query/say-hello.test.ts',
					excludes: 'holding',
					reason: 'no row about a child the root cannot hold',
				},
				{
					file: 'README.md',
					excludes: 'tx.helloWorld',
					reason: 'the readme shows no write the example does not have',
				},
			],
		})
		await assertScaffold({
			fixture: EXTENSION_FIXTURE,
			packageName: '@acme/extended',
			expectations: [
				{
					file: 'src/v1/config/namespaces.ts',
					includes: "default: { uri: 'urn:base'",
					reason: 'documents live in the namespace of their root element, not of the entry schema',
				},
				{
					file: 'src/v1/extensions/hello-world/transaction/ensure-part.test.ts',
					includes: "'/default:Root/default:Part'",
					reason: 'the root and its child are in the default namespace',
				},
			],
		})
		await assertScaffold({
			fixture: TWO_ROOTS_FIXTURE,
			packageName: '@acme/scores',
			options: ['--root', 'score-timewise'],
			expectations: [
				{
					file: 'src/v1/definition/constants.generated.ts',
					includes: "export const ROOT_ELEMENT = 'score-timewise' as const",
					reason: 'the chosen root is taken',
				},
				{
					file: 'src/v1/definition/constants.generated.ts',
					includes: "'score-timewise': ['choose', 'for-each']",
					reason: 'the members of a substitution group are the children, not their abstract head',
				},
				{
					file: 'package.json',
					includes: '--root score-timewise --entry',
					reason:
						'the generate script repeats the choice, so a regeneration reproduces the definition',
				},
			],
		})
		let refused = false
		try {
			await assertScaffold({
				fixture: TWO_ROOTS_FIXTURE,
				packageName: '@acme/undecided',
				expectations: [],
			})
		} catch (error) {
			refused = /--root/.test(String(error))
		}
		if (!refused)
			throw new Error('a schema with two possible roots must be refused until --root is given')
		console.log('Scaffold checks passed: engine range, namespace, project type, quoting, root.')

		await assertFailedScaffoldLeavesNothing()
		await assertHelpAndVersion()
		await assertRunsThroughABinLink()
		await assertInstalledScaffoldTypeChecks()
	} finally {
		await rm(outDir, { recursive: true, force: true })
	}
}

main().catch((err) => {
	console.error(`Smoke test failed: ${err instanceof Error ? err.message : String(err)}`)
	process.exit(1)
})
