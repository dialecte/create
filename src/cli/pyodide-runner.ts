import { readdir, mkdir } from 'node:fs/promises'
import { dirname, basename, resolve } from 'node:path'

import { formatGeneratedFiles } from './format-output.js'
import { PYTHON_ENGINE_DIR, VENDOR_DIR } from './paths.js'

import { loadPyodide, type PyodideInterface } from 'pyodide'

/** What a scaffold writes its worked example with, as the generator read it from the schema. */
export interface ExampleFacts {
	root: { name: string; namespaceUri: string }
	/** The first child the root allows; `null` when it allows none. */
	child: {
		name: string
		namespaceUri: string
		/** Each attribute the child requires, with a value the schema accepts. */
		requiredAttributes: { name: string; value: string }[]
	} | null
}

export interface GenerateOptions {
	/** Absolute path to the entry .xsd file. */
	entry: string
	/** Absolute path to the output directory for generated .ts files. */
	outDir: string
	/** Suppress engine stdout. */
	quiet?: boolean
	/** The element that starts a document, when more than one could. */
	root?: string
}

const GENERATED_FILES = ['definition.generated.ts', 'constants.generated.ts', 'types.generated.ts']

let pyodidePromise: Promise<PyodideInterface> | undefined

// Pyodide's bundled FS typings omit some Emscripten FS methods that exist at runtime.
interface EmscriptenFS {
	mkdir(path: string): void
	rmdir(path: string): void
	mount(type: unknown, opts: { root: string }, mountpoint: string): void
	unmount(mountpoint: string): void
	filesystems: { NODEFS: unknown }
}

function fs(py: PyodideInterface): EmscriptenFS {
	return py.FS as unknown as EmscriptenFS
}

async function getPyodide(quiet: boolean): Promise<PyodideInterface> {
	if (!pyodidePromise) {
		pyodidePromise = loadPyodide({
			stdout: quiet ? () => {} : (msg) => console.log(msg),
			stderr: (msg) => console.error(msg),
		})
	}
	return pyodidePromise
}

async function mountReadOnly(
	py: PyodideInterface,
	mountPoint: string,
	hostRoot: string,
): Promise<void> {
	const f = fs(py)
	try {
		f.mkdir(mountPoint)
	} catch {
		// already exists
	}
	f.mount(f.filesystems.NODEFS, { root: hostRoot }, mountPoint)
}

/** Mount points that stay the same for every run of this process. */
const permanentMounts = new Set<string>()

/**
 * The interpreter is kept between runs, and so are these mounts: mounting one of them a second
 * time is refused by the in-memory file system.
 */
async function mountOnce(
	py: PyodideInterface,
	mountPoint: string,
	hostRoot: string,
): Promise<void> {
	if (permanentMounts.has(mountPoint)) return
	await mountReadOnly(py, mountPoint, hostRoot)
	permanentMounts.add(mountPoint)
}

/**
 * Unmount and remove the work dirs of one run. Called from a `finally`: a failure here must not
 * hide the error of the run itself, and the next run mounts them again anyway.
 */
function releaseWorkMounts(py: PyodideInterface, mountPoints: string[]): void {
	const f = fs(py)
	for (const mountPoint of mountPoints) {
		try {
			f.unmount(mountPoint)
			f.rmdir(mountPoint)
		} catch (error) {
			console.warn(`Warning: could not release ${mountPoint}: ${String(error)}`)
		}
	}
}

async function listWheels(): Promise<string[]> {
	const entries = await readdir(VENDOR_DIR)
	return entries.filter((f) => f.endsWith('.whl'))
}

/**
 * Run the Python XSD->TypeScript generator inside Pyodide (WebAssembly).
 * No host Python installation is required.
 */
export async function runGenerator(options: GenerateOptions): Promise<ExampleFacts> {
	const { entry, outDir, quiet = false, root } = options

	const entryAbs = resolve(entry)
	const outAbs = resolve(outDir)
	const entryDir = dirname(entryAbs)
	const entryName = basename(entryAbs)

	await mkdir(outAbs, { recursive: true })

	const py = await getPyodide(quiet)

	// Engine source and vendored wheels.
	await mountOnce(py, '/engine', PYTHON_ENGINE_DIR)
	await mountOnce(py, '/vendor', VENDOR_DIR)

	// Pure-Python deps (xmlschema, elementpath) are extracted from their wheel
	// zips into the in-memory FS - fully offline, no micropip / CDN round-trip.
	// (Extraction is required because xmlschema reads bundled meta-schema .xsd
	// files via real filesystem paths, which zipimport can't serve.)
	const wheels = await listWheels()
	if (wheels.length === 0) {
		throw new Error(
			`No vendored wheels found in ${VENDOR_DIR}. Run "npm run vendor" to download them.`,
		)
	}
	const wheelPaths = JSON.stringify(wheels.map((w) => `/vendor/${w}`))

	// Invoke the engine CLI entry point with in-FS paths.
	const engineArgs = ['--entry', `/in/${entryName}`, '--out-dir', '/out']
	if (root !== undefined) engineArgs.push('--root', root)
	const argv = JSON.stringify(engineArgs)
	const workMounts: string[] = []
	let facts: unknown
	try {
		// Mount the entry XSD directory (handles relative imports/includes) and the output dir.
		await mountReadOnly(py, '/in', entryDir)
		workMounts.push('/in')
		await mountReadOnly(py, '/out', outAbs)
		workMounts.push('/out')

		facts = await py.runPythonAsync(`
import sys, os, zipfile

site_dir = '/site-packages'
if not os.path.isdir(site_dir):
    os.makedirs(site_dir, exist_ok=True)
    for wheel in ${wheelPaths}:
        with zipfile.ZipFile(wheel) as zf:
            zf.extractall(site_dir)

if site_dir not in sys.path:
    sys.path.insert(0, site_dir)
if '/engine' not in sys.path:
    sys.path.insert(0, '/engine')

from generate.__main__ import main
import json
json.dumps(main(${argv}))
`)
	} finally {
		// Unmount work dirs so subsequent runs can remount cleanly - a failed run included.
		releaseWorkMounts(py, workMounts)
	}

	formatGeneratedFiles({ outDir: outAbs, files: GENERATED_FILES })
	// the engine hands back, as JSON, what the scaffold names in its worked example
	return JSON.parse(String(facts)) as ExampleFacts
}
