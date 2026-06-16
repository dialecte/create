import { readdir, mkdir } from 'node:fs/promises'
import { dirname, basename, resolve } from 'node:path'
import { loadPyodide, type PyodideInterface } from 'pyodide'

import { PYTHON_ENGINE_DIR, VENDOR_DIR } from './paths.js'

export interface GenerateOptions {
	/** Absolute path to the entry .xsd file. */
	entry: string
	/** Absolute path to the output directory for generated .ts files. */
	outDir: string
	/** Suppress engine stdout. */
	quiet?: boolean
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

async function mountReadOnly(py: PyodideInterface, mountPoint: string, hostRoot: string): Promise<void> {
	const f = fs(py)
	try {
		f.mkdir(mountPoint)
	} catch {
		// already exists
	}
	f.mount(f.filesystems.NODEFS, { root: hostRoot }, mountPoint)
}

async function listWheels(): Promise<string[]> {
	const entries = await readdir(VENDOR_DIR)
	return entries.filter((f) => f.endsWith('.whl'))
}

/**
 * Run the Python XSD->TypeScript generator inside Pyodide (WebAssembly).
 * No host Python installation is required.
 */
export async function runGenerator(options: GenerateOptions): Promise<void> {
	const { entry, outDir, quiet = false } = options

	const entryAbs = resolve(entry)
	const outAbs = resolve(outDir)
	const entryDir = dirname(entryAbs)
	const entryName = basename(entryAbs)

	await mkdir(outAbs, { recursive: true })

	const py = await getPyodide(quiet)

	// Engine source and vendored wheels.
	await mountReadOnly(py, '/engine', PYTHON_ENGINE_DIR)
	await mountReadOnly(py, '/vendor', VENDOR_DIR)

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

	// Mount the entry XSD directory (handles relative imports/includes) and the output dir.
	await mountReadOnly(py, '/in', entryDir)
	await mountReadOnly(py, '/out', outAbs)

	// Invoke the engine CLI entry point with in-FS paths.
	const argv = JSON.stringify(['--entry', `/in/${entryName}`, '--out-dir', '/out'])
	await py.runPythonAsync(`
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
main(${argv})
`)

	// Unmount work dirs so subsequent runs can remount cleanly.
	const f = fs(py)
	f.unmount('/in')
	f.unmount('/out')
	f.rmdir('/in')
	f.rmdir('/out')
}
