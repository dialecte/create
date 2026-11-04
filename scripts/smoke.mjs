/**
 * CLI smoke test: run the WASM generator against a minimal fixture XSD and
 * assert the three definition files are produced. Exercises the full Pyodide
 * pipeline offline. Exits non-zero on failure.
 *
 * Usage: node scripts/smoke.mjs   (run after `npm run build` and `npm run vendor`)
 *
 * SMOKE_INSTALL=1 also installs a scaffolded package, type-checks it and runs its node tests (network,
 * slower): the only check that catches a generator ahead of the published engine, and that the template's
 * tests pass in node on it. DIALECTE_CORE=<core dir or
 * .tgz> installs that engine instead of the default range, to test against an unreleased core.
 */
import { spawnSync } from 'node:child_process'
import {
	copyFile,
	mkdtemp,
	readdir,
	rm,
	stat,
	readFile,
	symlink,
	writeFile,
} from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { stripVTControlCharacters } from 'node:util'

import { main as runCli, runGenerator } from '../dist/cli/index.js'

const FIXTURE = new URL('../test/fixtures/minimal.xsd', import.meta.url).pathname
const NO_NAMESPACE_FIXTURE = new URL('../test/fixtures/no-namespace.xsd', import.meta.url).pathname
const COMMENTED_FIXTURE = new URL('../test/fixtures/commented-namespace.xsd', import.meta.url)
	.pathname
const TWO_ROOTS_FIXTURE = new URL('../test/fixtures/two-roots.xsd', import.meta.url).pathname
const EXTENSION_FIXTURE = new URL('../test/fixtures/extension/entry.xsd', import.meta.url).pathname
const CORE_TEST_FIXTURE = new URL('../test/fixtures/xsd/core-test/test.xsd', import.meta.url)
	.pathname
const TEMPLATE_MANIFEST = new URL('../templates/dialecte/package.json', import.meta.url).pathname
/** The first @dialecte/cli with the `skills` command. */
const CLI_WITH_SKILLS = [0, 2, 0]
const EXPECTED = ['definition.generated.ts', 'constants.generated.ts', 'types.generated.ts']
const FIXTURES = new URL('../test/fixtures/', import.meta.url).pathname
const COMMITTED_SCHEMAS = JSON.parse(
	await readFile(join(FIXTURES, 'committed-schemas.json'), 'utf8'),
)

/**
 * Every committed schema regenerates, through the engine the CLI ships, the very files committed for it: the
 * definition the engine writes, the constants and types derived from it, formatted with the fixture's own
 * formatter configuration. The committed files are the reference every other test of the generator reads.
 */
async function assertCommittedFixturesRegenerate() {
	for (const [name, { entry, root }] of Object.entries(COMMITTED_SCHEMAS)) {
		const committed = join(FIXTURES, 'definition', name)
		const outDir = await mkdtemp(join(tmpdir(), `dialecte-regen-${name}-`))
		try {
			await copyFile(join(committed, '.oxfmtrc.json'), join(outDir, '.oxfmtrc.json'))
			await runGenerator({ entry: join(FIXTURES, 'xsd', name, entry), outDir, root, quiet: true })
			for (const file of EXPECTED) {
				const [regenerated, reference] = await Promise.all([
					readFile(join(outDir, file), 'utf8'),
					readFile(join(committed, file), 'utf8'),
				])
				if (regenerated !== reference) {
					throw new Error(
						`${name}/${file}: regenerating test/fixtures/xsd/${name} does not give the committed file - ` +
							`run the CLI on it and review the difference (npm run definition:diff for the definition)`,
					)
				}
			}
		} finally {
			await rm(outDir, { recursive: true, force: true })
		}
	}
	console.log(
		`Committed fixtures regenerate byte-identical: ${Object.keys(COMMITTED_SCHEMAS).join(', ')}.`,
	)
}

/** The value at `path` in a parsed JSON file, `undefined` when a step of it is missing. */
function valueAt({ document, path }) {
	return path.reduce(function step(value, key) {
		return value === undefined || value === null ? undefined : value[key]
	}, document)
}

/** A JSON value holds `item` among its entries. */
function listing(item) {
	return {
		description: `a list holding ${JSON.stringify(item)}`,
		test(value) {
			return Array.isArray(value) && value.includes(item)
		},
	}
}

/** The whitespace-separated words of a command: two runs that differ only in spacing are the same command. */
function tokensOf(command) {
	return typeof command === 'string' ? command.trim().split(/\s+/) : []
}

/**
 * A gate's step list is exactly `expected`, step by step: the same names in the same order, each run the same
 * words (a `--project browser-all` is not a `--project browser`), the other fields equal.
 */
function gateSteps(expected) {
	return {
		description: `the steps ${JSON.stringify(expected)}`,
		test(steps) {
			return (
				Array.isArray(steps) &&
				steps.length === expected.length &&
				expected.every(function stepMatches({ run, ...fields }, index) {
					const step = steps[index]
					const { run: actualRun, ...actualFields } = step ?? {}
					return (
						JSON.stringify(tokensOf(actualRun)) === JSON.stringify(tokensOf(run)) &&
						JSON.stringify(Object.entries(actualFields).sort()) ===
							JSON.stringify(Object.entries(fields).sort())
					)
				})
			)
		},
	}
}

/** What is wrong with one file against one expectation, or `undefined` when it holds. */
async function expectationFailure({ targetDir, packageName, expectation }) {
	const { file, includes, excludes, matches, notMatches, absent, json, equals, holds, reason } =
		expectation
	if ((equals !== undefined || holds !== undefined) && json === undefined) {
		throw new Error(`an expectation on ${file} with equals or holds needs the json path it reads`)
	}
	const path = join(targetDir, file)
	const exists = await stat(path).then(
		() => true,
		() => false,
	)
	if (absent) {
		return exists ? `${file} of ${packageName}: ${reason} (expected no such file)` : undefined
	}
	if (!exists) return `${file} of ${packageName}: ${reason} (expected the file, there is none)`
	const content = await readFile(path, 'utf8')
	if (includes !== undefined && !content.includes(includes)) {
		return `${file} of ${packageName}: ${reason} (expected to find ${JSON.stringify(includes)})`
	}
	if (excludes !== undefined && content.includes(excludes)) {
		return `${file} of ${packageName}: ${reason} (expected NOT to find ${JSON.stringify(excludes)})`
	}
	if (matches !== undefined && !matches.test(content)) {
		return `${file} of ${packageName}: ${reason} (expected to match ${matches})`
	}
	if (notMatches !== undefined && notMatches.test(content)) {
		return `${file} of ${packageName}: ${reason} (expected NOT to match ${notMatches})`
	}
	if (json !== undefined) {
		const value = valueAt({ document: JSON.parse(content), path: json })
		const where = `${file} of ${packageName} at ${json.join('.')}`
		if (equals !== undefined && JSON.stringify(value) !== JSON.stringify(equals)) {
			return `${where}: ${reason} (expected ${JSON.stringify(equals)}, got ${JSON.stringify(value)})`
		}
		if (holds !== undefined && !holds.test(value)) {
			return `${where}: ${reason} (expected ${holds.description}, got ${JSON.stringify(value)})`
		}
	}
	return undefined
}

/**
 * Scaffold a package and check what a consumer relies on in the files it gets. Every expectation is checked and
 * every failed one reported, so one run shows all that is wrong.
 */
async function assertScaffold({ fixture, packageName, expectations, options = [] }) {
	const targetDir = await mkdtemp(join(tmpdir(), 'dialecte-scaffold-'))
	try {
		await runCli(['create', fixture, '--name', packageName, '--out', targetDir, ...options])
		const failures = []
		for (const expectation of expectations) {
			const failure = await expectationFailure({ targetDir, packageName, expectation })
			if (failure !== undefined) failures.push(failure)
		}
		if (failures.length > 0) {
			throw new Error(
				`${failures.length} scaffold expectation(s) failed:\n${failures
					.map(function bullet(failure) {
						return `  - ${failure}`
					})
					.join('\n')}`,
			)
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

/** A flag a command does not take is refused by name, before anything is written - never ignored. */
async function assertUnknownFlagRefused() {
	const parent = await mkdtemp(join(tmpdir(), 'dialecte-flag-'))
	const targetDir = join(parent, 'pkg')
	try {
		const refusal = await runCli([
			'create',
			FIXTURE,
			'--namespace',
			'urn:x',
			'--out',
			targetDir,
		]).then(
			() => undefined,
			(error) => (error instanceof Error ? error.message : String(error)),
		)
		if (refusal === undefined || !refusal.includes('--namespace')) {
			throw new Error(`create --namespace should be refused by name, got: ${refusal ?? 'success'}`)
		}
		const left = await stat(targetDir).then(
			() => true,
			() => false,
		)
		if (left) throw new Error(`a refused flag left ${targetDir} behind`)
		console.log('A flag a command does not take is refused by name.')
	} finally {
		await rm(parent, { recursive: true, force: true })
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

/** The test files of a scaffold: every `*.test.ts` under its `src/`. */
async function testFilesOf(targetDir) {
	const entries = await readdir(join(targetDir, 'src'), { recursive: true })
	return entries.filter(function isTestFile(entry) {
		return entry.endsWith('.test.ts')
	})
}

/**
 * The number of tests vitest's summary says passed, once it says every test file of the scaffold passed. A run with
 * no count, a count of zero, or fewer files than the scaffold holds tested less than the package: a failure, not a
 * pass.
 */
function nodeTestsPassed({ output, testFiles }) {
	const text = stripVTControlCharacters(output)
	const files = text.match(/^\s*Test Files\s+(\d+) passed \((\d+)\)/m)
	if (files === null || Number(files[1]) !== testFiles || Number(files[2]) !== testFiles) {
		throw new Error(
			`npm run test:node of the scaffold must pass its ${testFiles} test files, its summary says ${files === null ? 'no file count' : JSON.stringify(files[0].trim())}:\n${text}`,
		)
	}
	const summary = text.match(/^\s*Tests\s+(\d+) passed/m)
	const passed = summary === null ? 0 : Number(summary[1])
	if (passed === 0) {
		throw new Error(`npm run test:node of the scaffold ran no test:\n${text}`)
	}
	return passed
}

/** A listed test file to name no file: the vitest config must refuse it. */
const MISSING_LISTED_TEST_FILE = 'src/missing.test.ts'

/**
 * The vitest config refuses a tier list naming a file that does not exist: a moved test file must not drop out of its
 * tier unseen. The scaffold's `listName` list gets a missing path for one `vitest list`, then its file is put back.
 */
async function assertMissingListedTestFileRefused({ targetDir, listName }) {
	const constantsPath = join(targetDir, 'vitest.config.constants.ts')
	const original = await readFile(constantsPath, 'utf8').catch(function noConstantsFile() {
		return undefined
	})
	const emptyList = new RegExp(`(export const ${listName}\\b[^=]*= )\\[\\]`)
	if (original === undefined || !emptyList.test(original)) {
		throw new Error(
			`vitest.config.constants.ts of the scaffold has no empty ${listName} list to list a missing file in`,
		)
	}
	try {
		await writeFile(
			constantsPath,
			original.replace(
				emptyList,
				`$1[{ path: '${MISSING_LISTED_TEST_FILE}', why: 'smoke: a path naming no file' }]`,
			),
		)
		const result = spawnSync('npx', ['vitest', 'list', '--project', 'node'], {
			cwd: targetDir,
			encoding: 'utf8',
			stdio: 'pipe',
			env: { ...process.env, NO_COLOR: '1' },
		})
		const output = stripVTControlCharacters(`${result.stdout}\n${result.stderr}`)
		if (result.status === 0 || !output.includes(MISSING_LISTED_TEST_FILE)) {
			throw new Error(
				`the vitest config of the scaffold must refuse a ${listName} entry that names no file (${MISSING_LISTED_TEST_FILE}), got exit ${result.status}:\n${output}`,
			)
		}
		return `The vitest config of the scaffold refuses a ${listName} entry that names no file.`
	} finally {
		await writeFile(constantsPath, original)
	}
}

/**
 * The skill the scaffold ships matches what the generator renders from the installed package. Skipped only while
 * the template pins a cli older than the one with the skills command; from then on a failing check fails the smoke.
 */
async function assertInstalledSkillsCheck(targetDir) {
	const template = JSON.parse(await readFile(TEMPLATE_MANIFEST, 'utf8'))
	const pinned =
		template.devDependencies?.['@dialecte/cli'] ?? template.dependencies?.['@dialecte/cli']
	if (pinned === undefined) throw new Error('The template does not depend on @dialecte/cli')
	if (isBelowVersion({ version: pinned, minimum: CLI_WITH_SKILLS })) {
		return `Skills check skipped: the template pins @dialecte/cli ${pinned}, the skills command ships in ${CLI_WITH_SKILLS.join('.')}.`
	}
	run('npx', ['dialecte', 'skills', 'check'], targetDir)
	return 'Installed scaffold: its skill checks green.'
}

/** `0.0.3`, `^0.2.0` or `~1.4.2` against `[major, minor, patch]`: the range's lowest version decides. */
function isBelowVersion({ version, minimum }) {
	const parts = version
		.replace(/^[\^~=v]+/, '')
		.split('.')
		.map(Number)
	if (parts.length !== 3 || parts.some(Number.isNaN)) {
		throw new Error(
			`Cannot read the @dialecte/cli version ${JSON.stringify(version)} of the template`,
		)
	}
	const differing = parts.findIndex((part, index) => part !== minimum[index])
	return differing !== -1 && parts[differing] < minimum[differing]
}

/**
 * A scaffolded package must install and compile against the engine it targets, and its own tests must pass in node
 * on it.
 */
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
		const engine = core || 'default range'
		const testFiles = (await testFilesOf(targetDir)).length
		const failures = []
		// each step runs whatever the one before gave, so one run shows every step that fails
		for (const step of [
			function typeChecks() {
				run('npm', ['run', 'type-check'], targetDir)
				return `Installed scaffold type-checks (engine: ${engine}).`
			},
			function testsTypeCheck() {
				run('npm', ['run', 'type-check:test'], targetDir)
				return `Installed scaffold type-checks its tests (engine: ${engine}).`
			},
			function nodeConfigsTypeCheck() {
				run('npm', ['run', 'type-check:node'], targetDir)
				return `Installed scaffold type-checks its Node configs (engine: ${engine}).`
			},
			function skillsCheck() {
				return assertInstalledSkillsCheck(targetDir)
			},
			function nodeTestsPass() {
				const output = run('npm', ['run', 'test:node'], targetDir)
				const passed = nodeTestsPassed({ output, testFiles })
				return `Installed scaffold passes its node tests: ${testFiles} file(s), ${passed} test(s) (engine: ${engine}).`
			},
			function missingBrowserOnlyTestFileRefused() {
				return assertMissingListedTestFileRefused({
					targetDir,
					listName: 'BROWSER_ONLY_TEST_FILES',
				})
			},
			function missingNodeOnlyTestFileRefused() {
				return assertMissingListedTestFileRefused({ targetDir, listName: 'NODE_ONLY_TEST_FILES' })
			},
		]) {
			try {
				console.log(await step())
			} catch (error) {
				failures.push(error instanceof Error ? error.message : String(error))
			}
		}
		if (failures.length > 0) throw new Error(failures.join('\n'))
	} finally {
		await rm(parent, { recursive: true, force: true })
	}
}

/** Every scaffold expectation, each scaffold checked in full. */
async function assertScaffolds() {
	await assertScaffold({
		fixture: FIXTURE,
		packageName: '@acme/widget',
		expectations: [
			{
				file: 'package.json',
				includes: '"@dialecte/core": "^0.8.',
				reason: 'the engine range must target the current release line',
			},
			{
				file: 'package.json',
				includes: '"type-check": "tsc -p tsconfig.build.json --noEmit"',
				reason: 'the root tsconfig only references the others, so checking it checks nothing',
			},
			{
				file: 'package.json',
				includes: '"type-check:node": "tsc -p tsconfig.node.json --noEmit"',
				reason: 'the Vite and Vitest configs run in Node and are type-checked on their own',
			},
			{
				file: 'package.json',
				includes: '"check": "run-p type-check type-check:test type-check:node ',
				reason: 'check type-checks the Node configs too, or an error there goes unseen',
			},
			{
				file: 'vite.config.ts',
				includes: "sourcemap: process.env.NODE_ENV === 'development',",
				reason: 'a Vite config runs in Node, where import.meta.env is undefined',
			},
			{
				file: 'vite.config.ts',
				excludes: 'vite/client',
				reason: 'the client types would declare import.meta.env in a file that runs in Node',
			},
			{
				file: 'src/v1/config/namespaces.ts',
				includes: "uri: 'urn:dialecte:example'",
				reason: 'the default namespace must be the target namespace of the schema',
			},
			{
				file: 'src/v1/config/namespaces.ts',
				excludes: '__prefixedNamespaces__',
				reason: 'a schema of one namespace declares no other',
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
				file: 'skills/dialecte-widget/SKILL.md',
				includes: 'name: dialecte-widget',
				reason: 'a generated dialecte ships the agent skill that describes it, named after its id',
			},
			{
				file: 'skills/dialecte-widget/SKILL.md',
				matches: /\| `helloWorld` +\| `sayHello` +\| `ensure\w+` +\|/,
				reason:
					'the skill ships with its verb map filled as the generator renders it, so check passes before any edit',
			},
			{
				file: 'skills/dialecte-widget/SKILL.md',
				includes: 'This package has no hooks.',
				reason: 'a new package has no hooks folder: the generated hooks block says so',
			},
			{
				file: 'skills/dialecte-widget/SKILL.md',
				excludes: '__',
				reason: 'no placeholder or conditional marker is left in the skill',
			},
			{
				file: 'skills/dialecte-widget/references/api.md',
				excludes: '__',
				reason: 'no placeholder or conditional marker is left in the API index',
			},
			{
				file: 'skills/dialecte-widget/references/api.md',
				matches:
					/\| `doc\.query\.helloWorld\.sayHello` +\| The smallest useful read: what is this document made of\? +\| count what a document is made of; example of a read extension +\|/,
				reason: 'the API index row is the JSDoc of the example as the generator renders it',
			},
			{
				file: 'package.json',
				includes: '"skills:check": "dialecte skills check"',
				reason: 'the check gate fails when the skill cites what the code no longer has',
			},
			{
				file: 'package.json',
				includes: '"!skills/*/evals"',
				reason: 'the skill ships in the tarball, its maintainer evals do not',
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
			// two test tiers: every unit test in node on the in-memory store, the browser for what needs one
			{
				file: 'package.json',
				json: ['scripts', 'test'],
				equals: 'npm run test:node && npm run test:browser',
				reason: 'npm test runs the node tier, then the browser-only tests',
			},
			{
				file: 'package.json',
				json: ['scripts', 'test:node'],
				equals: 'vitest run --project node',
				reason: 'the node tier has its own script',
			},
			{
				file: 'package.json',
				json: ['scripts', 'test:browser'],
				equals: 'vitest run --project browser --passWithNoTests',
				reason: 'the browser-only tests have their own script, and none is no failure',
			},
			{
				file: 'package.json',
				json: ['scripts', 'test:browser:all'],
				equals: 'vitest run --project browser-all',
				reason: 'the whole suite runs in the browser before a merge',
			},
			{
				file: 'package.json',
				json: ['dialecte', 'gate', 'fast'],
				holds: gateSteps([
					{ name: 'check', run: 'npm run check' },
					{ name: 'skills', run: 'npm run skills:check' },
					{
						name: 'tests',
						run: 'npx vitest run --project node --changed',
						counts: 'tests',
						changedOnly: true,
					},
				]),
				reason:
					'the fast gate checks, checks the skills, then runs the changed node tests and counts them',
			},
			{
				file: 'package.json',
				json: ['dialecte', 'gate', 'full'],
				holds: gateSteps([
					{ name: 'check', run: 'npm run check' },
					{ name: 'skills', run: 'npm run skills:check' },
					{ name: 'build', run: 'npm run build' },
					{
						name: 'tests',
						run: 'nice -n 10 npx vitest run --project node --maxWorkers=2',
						counts: 'tests',
					},
					{
						name: 'browser tests',
						run: 'nice -n 10 npx vitest run --project browser --passWithNoTests --no-file-parallelism',
					},
					{ name: 'docs', run: 'npm run doc:build' },
					{ name: 'type-bench', run: 'npm run type-bench:check' },
				]),
				reason:
					'the full gate checks, checks the skills, builds, runs every node test gently and counts them, the browser-only tests one file at a time, the docs and the type bench',
			},
			{
				file: 'package.json',
				json: ['dialecte', 'tdd', 'production'],
				equals: ['src/v1/test'],
				reason: 'the test helpers of the package are production code for the red-green receipts',
			},
			{
				file: 'vitest.config.ts',
				includes: "environment: 'node'",
				reason: 'the node project runs in node, no DOM',
			},
			{
				file: 'vitest.config.ts',
				includes: 'src/v1/test/in-memory-storage.setup.ts',
				reason: 'the node project opens its test projects on the in-memory store',
			},
			{
				file: 'vitest.config.ts',
				includes: 'pathsOf({ project: BROWSER_PROJECT, files: BROWSER_ONLY_TEST_FILES })',
				reason: 'the browser-only list goes through the check that refuses a path naming no file',
			},
			{
				file: 'vitest.config.ts',
				includes: 'pathsOf({ project: BROWSER_ALL_PROJECT, files: NODE_ONLY_TEST_FILES })',
				reason: 'the node-only list goes through the check that refuses a path naming no file',
			},
			{
				file: 'vitest.config.constants.ts',
				matches: /export const BROWSER_ONLY_TEST_FILES\b[^=]*= \[\]/,
				reason: 'the browser-only test files are listed in one place, none in a new package',
			},
			{
				file: 'vitest.config.constants.ts',
				matches: /export const NODE_ONLY_TEST_FILES\b[^=]*= \[\]/,
				reason: 'the node-only test files are listed in one place, none in a new package',
			},
			{
				file: 'src/v1/test/in-memory-storage.setup.ts',
				includes: "useTestStorage({ type: 'inMemory' })",
				reason: 'the setup of the node project selects the in-memory store',
			},
			{
				file: 'tsconfig.build.json',
				json: ['exclude'],
				holds: listing('src/**/*.setup.ts'),
				reason: 'a test setup file is not part of the built package',
			},
			{
				file: 'tsconfig.vitest.json',
				json: ['include'],
				holds: listing('src/**/*.setup.ts'),
				reason: 'a test setup file is type-checked with the tests',
			},
			{
				file: '.github/workflows/_test.yml',
				matches: /run: npm run test:node\s*$[\s\S]*run: npm run test:browser:all\s*$/m,
				reason: 'CI runs the node tier, then the whole suite in the browser',
			},
			{
				file: '.github/workflows/_test.yml',
				notMatches: /run: npm (run )?test\s*$/m,
				reason: 'CI no longer runs the browser-only default test script',
			},
			{
				file: 'src/v1/test/hydrated-test.ts',
				includes:
					"assertValidWidgetXml({ xml: sourceXml, label: 'sourceXml', requireComplete: false })",
				reason: "a test project's source is checked with core's one-object assertValidXml",
			},
			{
				file: 'src/v1/test/hydrated-test.ts',
				includes:
					"assertValidWidgetXml({ xml: targetXml, label: 'targetXml', requireComplete: false })",
				reason: "a test project's target is checked with core's one-object assertValidXml",
			},
			{
				file: 'src/v1/test/hydrated-test.ts',
				excludes: 'export const XMLNS_WIDGET_NAMESPACE',
				reason: 'the xmlns constants live in their own constants file',
			},
			{
				file: 'src/v1/test/hydrated-test.ts',
				includes: "from './xmlns.constants'",
				reason: 'the test entry re-exports the xmlns constants from their file',
			},
			{
				file: 'src/v1/test/hydrated-test.ts',
				excludes: 'type WidgetModules = typeof WIDGET_EXTENSION_MODULES',
				reason: 'no local alias of the modules type: WidgetTest.Modules is the one',
			},
			{
				file: 'src/v1/test/hydrated-test.ts',
				includes: 'createTestRunner<Config, WidgetTest.Modules>(',
				reason: 'the test runner is typed with the namespace modules type',
			},
			{
				file: 'src/v1/test/hydrated-test.ts',
				includes: 'createTestProject<Config, WidgetTest.Modules>(',
				reason: 'the test project is typed with the namespace modules type',
			},
			{
				file: 'src/v1/test/xmlns.constants.ts',
				includes: 'export const XMLNS_WIDGET_NAMESPACE',
				reason: 'the default namespace of a fixture root is a constant of its own file',
			},
			{
				file: 'src/v1/test/xmlns.constants.ts',
				includes: 'export const ALL_XMLNS_NAMESPACES',
				reason: 'every namespace a fixture root declares is a constant of the same file',
			},
			{
				file: 'src/v1/test/hydrated-test.types.ts',
				includes: 'export type Modules = typeof WIDGET_EXTENSION_MODULES',
				reason: 'the extension modules are typed once, as WidgetTest.Modules',
			},
			{
				file: 'README.md',
				excludes: '# vitest (browser)',
				reason: 'the tests no longer run only in the browser',
			},
			{
				file: 'README.md',
				includes: 'npm run test:node',
				reason: 'the readme gives the command of each test tier',
			},
			{
				file: 'README.md',
				includes: "useTestStorage({ type: 'inMemory' })",
				reason: 'a consumer of the test helpers runs them in node with its own in-memory setup',
			},
			{
				file: 'README.md',
				includes: 'npm run test:browser:all',
				reason: 'the readme gives the command of the whole suite in the browser',
			},
			{
				file: 'docs/index.md',
				includes: 'npm run test:node',
				reason: 'the docs give the command of each test tier',
			},
			{
				file: 'docs/index.md',
				includes: 'useTestStorage',
				reason: 'the docs tell a consumer of the test helpers to select the in-memory store',
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
		options: ['--core-version', '-next'],
		expectations: [
			{
				file: 'package.json',
				includes: '"@dialecte/core": "-next"',
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
			{
				file: 'skills/dialecte-quoted/SKILL.md',
				matches: /\| `helloWorld` +\| `sayHello` +\| - +\|/,
				reason: 'the verb map of the skill lists no write the example does not have',
			},
			{
				file: 'skills/dialecte-quoted/SKILL.md',
				excludes: '__',
				reason: 'no placeholder or conditional marker is left in the skill of a root without child',
			},
			{
				file: 'skills/dialecte-quoted/references/api.md',
				excludes: '__',
				reason:
					'no placeholder or conditional marker is left in the API index of a root without child',
			},
			{
				file: 'skills/dialecte-quoted/references/api.md',
				excludes: 'ensure',
				reason: 'the API index lists no write the example does not have',
			},
		],
	})
	await assertScaffold({
		fixture: CORE_TEST_FIXTURE,
		packageName: '@acme/prefixed',
		expectations: [
			{
				file: 'src/v1/config/namespaces.ts',
				includes: "\text: { uri: 'http://dialecte.dev/XML/DEV-EXT', prefix: 'ext' },",
				reason:
					'every namespace the definition prefixes is declared with that prefix: core stores xsi:type values with it',
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

		await assertCommittedFixturesRegenerate()

		const failures = []
		for (const check of [
			assertScaffolds,
			assertFailedScaffoldLeavesNothing,
			assertUnknownFlagRefused,
			assertHelpAndVersion,
			assertRunsThroughABinLink,
			assertInstalledScaffoldTypeChecks,
		]) {
			try {
				await check()
			} catch (error) {
				// every check runs, so one run shows each that fails
				failures.push(`${check.name}: ${error instanceof Error ? error.message : String(error)}`)
			}
		}
		if (failures.length > 0) throw new Error(failures.join('\n\n'))
	} finally {
		await rm(outDir, { recursive: true, force: true })
	}
}

main().catch((err) => {
	console.error(`Smoke test failed: ${err instanceof Error ? err.message : String(err)}`)
	process.exit(1)
})
