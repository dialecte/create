/**
 * Download the pure-Python wheels the generator needs into ./vendor.
 *
 * These are installed offline inside Pyodide at runtime via micropip, so the
 * published CLI never touches the network. Re-run when bumping dependency
 * versions. Requires network access.
 *
 * Usage: node scripts/vendor-wheels.mjs
 */
import { mkdir, writeFile, readdir, rm } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const vendorDir = join(here, '..', 'vendor')

// Pure-Python deps of the generator. Pinned for reproducible offline installs.
const PACKAGES = [
	{ name: 'elementpath', version: '5.1.1' },
	{ name: 'xmlschema', version: '4.3.1' },
]

/** Resolve the py3-none-any wheel metadata from the PyPI JSON API. */
async function resolveWheel(name, version) {
	const res = await fetch(`https://pypi.org/pypi/${name}/${version}/json`)
	if (!res.ok) {
		throw new Error(`PyPI lookup failed for ${name}==${version}: ${res.status}`)
	}
	const data = await res.json()
	const wheel = data.urls.find(
		(u) => u.packagetype === 'bdist_wheel' && u.filename.endsWith('-py3-none-any.whl'),
	)
	if (!wheel) {
		throw new Error(`No py3-none-any wheel found for ${name}==${version}`)
	}
	return wheel
}

async function main() {
	await mkdir(vendorDir, { recursive: true })

	for (const f of await readdir(vendorDir)) {
		if (f.endsWith('.whl')) await rm(join(vendorDir, f))
	}

	for (const pkg of PACKAGES) {
		const wheel = await resolveWheel(pkg.name, pkg.version)
		console.log(`Downloading ${wheel.filename}`)
		const res = await fetch(wheel.url)
		if (!res.ok) {
			throw new Error(`Failed to download ${wheel.url}: ${res.status} ${res.statusText}`)
		}
		const buf = Buffer.from(await res.arrayBuffer())
		await writeFile(join(vendorDir, wheel.filename), buf)
	}

	console.log(`Vendored ${PACKAGES.length} wheels into ${vendorDir}`)
}

main().catch((err) => {
	console.error(err)
	process.exit(1)
})
