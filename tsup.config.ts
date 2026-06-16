import { defineConfig } from 'tsup'

export default defineConfig({
	entry: ['src/cli/index.ts'],
	format: ['esm'],
	target: 'node20',
	platform: 'node',
	outDir: 'dist/cli',
	clean: true,
	splitting: false,
	sourcemap: false,
	// pyodide is resolved at runtime from node_modules (loads its own wasm assets)
	external: ['pyodide'],
	banner: {
		js: '#!/usr/bin/env node',
	},
})
