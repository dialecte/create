import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

// Resolved at runtime relative to the built CLI entry (dist/cli/index.js).
// Package root is two levels up from dist/cli.
const here = dirname(fileURLToPath(import.meta.url))

export const PACKAGE_ROOT = resolve(here, '..', '..')
export const PYTHON_ENGINE_DIR = resolve(PACKAGE_ROOT, 'python')
export const VENDOR_DIR = resolve(PACKAGE_ROOT, 'vendor')
export const TEMPLATES_DIR = resolve(PACKAGE_ROOT, 'templates')
