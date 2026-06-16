import path from 'node:path'
/// <reference types="vite/client" />
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import dts from 'vite-plugin-dts'

export default defineConfig({
	plugins: [
		dts({
			tsconfigPath: path.resolve(__dirname, './tsconfig.build.json'),
			insertTypesEntry: true,
		}),
	],
	resolve: {
		alias: {
			'@': fileURLToPath(new URL('./src', import.meta.url)),
		},
	},
	build: {
		sourcemap: import.meta.env?.DEV,
		lib: {
			entry: {
				'__version__/index': fileURLToPath(new URL('./src/__version__/index.ts', import.meta.url)),
				'__version__/test': fileURLToPath(new URL('./src/__version__/test/index.ts', import.meta.url)),
			},
			name: '__DialecteName__Dialecte',
			formats: ['es'],
		},
		rollupOptions: {
			external: [/^@dialecte\/core/],
		},
	},
})
