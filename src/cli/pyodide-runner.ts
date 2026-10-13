import { readdir } from 'node:fs/promises'
import { parse, relative, resolve, sep } from 'node:path'

import { engineError } from './engine-error.ts'
import { PYTHON_ENGINE_DIR, VENDOR_DIR } from './paths.ts'
import { writeGenerated } from './write-generated.ts'

import { loadPyodide, type PyodideInterface } from 'pyodide'

import type { GeneratedFacts } from '../derive/derive.types.ts'
import type { GeneratedDefinition } from './write-generated.types.ts'

export type { ExampleFacts, GeneratedFacts } from '../derive/derive.types.ts'

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

/** Mount a host folder (NODEFS) at `mountPoint`; the engine only reads from it. */
async function mountHost(
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
	await mountHost(py, mountPoint, hostRoot)
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
 * Run the Python schema reader inside Pyodide (WebAssembly) - no host Python installation is required -, then
 * write the definition it returns with the constants and types derived from it, and return what the scaffold needs
 * (`GeneratedFacts`).
 */
export async function runGenerator(options: GenerateOptions): Promise<GeneratedFacts> {
	const { entry, outDir, quiet = false, root } = options

	const entryAbs = resolve(entry)
	// the root of the entry's file system: a schema may import or include from above its own folder
	const hostRoot = parse(entryAbs).root
	const entryInFs = `/in/${relative(hostRoot, entryAbs).split(sep).join('/')}`

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

	// The engine reads the schema from the in-FS path of its entry; it writes nothing.
	const entryPath = JSON.stringify(entryInFs)
	const workMounts: string[] = []
	let generated: unknown
	try {
		await mountHost(py, '/in', hostRoot)
		workMounts.push('/in')

		generated = await py.runPythonAsync(`
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

from generate.__main__ import generate
import json, pathlib
json.dumps(generate(pathlib.Path(${entryPath})))
`)
	} catch (error) {
		throw engineError(error, (text) => text.replaceAll('/in/', hostRoot.split(sep).join('/')))
	} finally {
		// Unmount work dirs so subsequent runs can remount cleanly - a failed run included.
		releaseWorkMounts(py, workMounts)
	}

	// the engine hands back, as JSON, the definition, its types and their source: the rest derives from them
	return writeGenerated({
		outDir,
		generated: JSON.parse(String(generated)) as GeneratedDefinition,
		root,
	})
}
