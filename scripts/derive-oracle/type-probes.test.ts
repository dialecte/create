import assert from 'node:assert/strict'
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

import { emittedFiles } from './check-emitted.ts'
import { compileWithTsc, compileWithTsgo, typeCheck, typeProbesSource } from './type-probes.ts'

import type { DefinitionData, TypesData } from '../../src/derive/derive.types.ts'
import type { Compiled } from './type-probes.types.ts'

/** A committed fixture's definition, as its generated file exports it. */
type Generated = { DEFINITION: DefinitionData; TYPES: TypesData }

const FIXTURES = fileURLToPath(new URL('../../test/fixtures/definition/', import.meta.url))
const GENERATED = ['definition.generated.ts', 'constants.generated.ts', 'types.generated.ts']

/** A fixture's generated files and its probes in a scratch folder; `tamper` edits the types file first. */
function probed(params: { fixture: string; tamper?: (types: string) => string }): string {
	const { fixture, tamper = (types) => types } = params
	const folder = mkdtempSync(join(tmpdir(), `probes-${fixture}-`))
	for (const file of GENERATED) copyFileSync(join(FIXTURES, fixture, file), join(folder, file))
	writeFileSync(
		join(folder, 'types.generated.ts'),
		tamper(readFileSync(join(folder, 'types.generated.ts'), 'utf-8')),
	)
	return folder
}

/** The probes of a committed fixture, read with the root its constants were written for. */
async function fixtureProbes(fixture: string): Promise<string> {
	const { DEFINITION, TYPES } = (await import(
		join(FIXTURES, fixture, 'definition.generated.ts')
	)) as Generated
	const { ROOT_ELEMENT } = (await import(join(FIXTURES, fixture, 'constants.generated.ts'))) as {
		ROOT_ELEMENT: string
	}
	return typeProbesSource({ definition: DEFINITION, types: TYPES, root: ROOT_ELEMENT })
}

describe('type probes', () => {
	for (const fixture of ['core-test', 'homonym', 'torture']) {
		it(`${fixture}: the generated types accept and refuse what the definition says`, async () => {
			const folder = probed({ fixture })
			try {
				writeFileSync(join(folder, 'probes.ts'), await fixtureProbes(fixture))
				assert.deepEqual(typeCheck({ folders: [folder] }), [])
			} finally {
				rmSync(folder, { recursive: true, force: true })
			}
		})
	}

	it('a required attribute the types make optional -> the probe fails', async () => {
		// AttributesA declares `aA: string`, required: made optional, the missing-attribute probe must catch it
		const folder = probed({
			fixture: 'core-test',
			tamper: (types) => types.replace('\taA: ', '\taA?: '),
		})
		try {
			writeFileSync(join(folder, 'probes.ts'), await fixtureProbes('core-test'))
			assert.deepEqual(typeCheck({ folders: [folder] }), [folder])
		} finally {
			rmSync(folder, { recursive: true, force: true })
		}
	})

	it('a type open to any key -> the unknown-attribute probe fails', async () => {
		const folder = probed({
			fixture: 'core-test',
			tamper: (types) =>
				types.replace(
					'export type AttributesA = {',
					'export type AttributesA = {\n\t[key: string]: string',
				),
		})
		try {
			writeFileSync(join(folder, 'probes.ts'), await fixtureProbes('core-test'))
			assert.deepEqual(typeCheck({ folders: [folder] }), [folder])
		} finally {
			rmSync(folder, { recursive: true, force: true })
		}
	})

	const unionTampers: Record<string, (types: string) => string> = {
		'an abstract type given a member of its own -> the probe fails': (types) =>
			types.replace(
				'export type AttributesDD_1 = Exclusive<\n',
				'export type AttributesDD_1 = Exclusive<\n\t| { aDD_1: string }\n',
			),
		'a type of another namespace named by its local name (the old hint) -> the probe fails': (
			types,
		) => types.replace("'xsi:type': 'ext:tDD_1A'", "'xsi:type': 'tDD_1A'"),
		'a union not exclusive (a member open to the attributes of another type) -> the probe fails': (
			types,
		) =>
			types.replace(
				'export type AttributesDD_2 = Exclusive<',
				'type Plain<Members> = Members\nexport type AttributesDD_2 = Plain<',
			),
		'an own member open to any xsi:type -> the probe fails': (types) =>
			types.replace("'xsi:type'?: 'tDD_2'", "'xsi:type'?: string"),
	}
	for (const [name, tamper] of Object.entries(unionTampers)) {
		it(name, async () => {
			const folder = probed({ fixture: 'core-test', tamper })
			try {
				assert.notEqual(
					readFileSync(join(folder, 'types.generated.ts'), 'utf-8'),
					readFileSync(join(FIXTURES, 'core-test', 'types.generated.ts'), 'utf-8'),
					'the tamper changed nothing',
				)
				writeFileSync(join(folder, 'probes.ts'), await fixtureProbes('core-test'))
				assert.deepEqual(typeCheck({ folders: [folder] }), [folder])
			} finally {
				rmSync(folder, { recursive: true, force: true })
			}
		})
	}

	it('tsgo -> the verdicts of tsc: a fixture passes, a tampered one fails', async () => {
		const sound = probed({ fixture: 'torture' })
		const broken = probed({
			fixture: 'core-test',
			tamper: (types) => types.replace("'xsi:type'?: 'tDD_2'", "'xsi:type'?: string"),
		})
		try {
			writeFileSync(join(sound, 'probes.ts'), await fixtureProbes('torture'))
			writeFileSync(join(broken, 'probes.ts'), await fixtureProbes('core-test'))
			for (const compile of [compileWithTsc, compileWithTsgo]) {
				assert.deepEqual(typeCheck({ folders: [sound, broken], compile }), [broken], compile.name)
			}
		} finally {
			rmSync(sound, { recursive: true, force: true })
			rmSync(broken, { recursive: true, force: true })
		}
	})

	it('folders whose names prefix one another -> only the failing one', async () => {
		const root = mkdtempSync(join(tmpdir(), 'probes-prefix-'))
		try {
			const [ok, broken] = [join(root, '1'), join(root, '10')]
			for (const [folder, tamper] of [
				[ok, (types: string) => types],
				[broken, (types: string) => types.replace('\taA: ', '\taA?: ')],
			] as const) {
				mkdirSync(folder)
				for (const file of GENERATED)
					copyFileSync(join(FIXTURES, 'core-test', file), join(folder, file))
				writeFileSync(
					join(folder, 'types.generated.ts'),
					tamper(readFileSync(join(folder, 'types.generated.ts'), 'utf-8')),
				)
				writeFileSync(join(folder, 'probes.ts'), await fixtureProbes('core-test'))
			}
			assert.deepEqual(typeCheck({ folders: [ok, broken] }), [broken])
		} finally {
			rmSync(root, { recursive: true, force: true })
		}
	})

	it('a schema whose elements hold no child -> its files and probes type-check (no per-parent probe to import)', () => {
		const definition: DefinitionData = {
			Root: {
				parents: [],
				global: true,
				attributes: { sequence: ['a'], details: { a: { required: true } } },
				children: { sequence: [], details: {} },
			},
		}
		const folder = mkdtempSync(join(tmpdir(), 'probes-leaf-'))
		try {
			writeFileSync(
				join(folder, 'definition.generated.ts'),
				'export const DEFINITION = {}\nexport const TYPES = {}\n',
			)
			for (const [name, text] of Object.entries(emittedFiles({ definition, types: {} }) ?? {}))
				writeFileSync(join(folder, name), text)
			assert.deepEqual(typeCheck({ folders: [folder] }), [])
		} finally {
			rmSync(folder, { recursive: true, force: true })
		}
	})

	it('a batch tsc cannot hold (it crashes) -> split until each folder is judged, only the failing one reported', () => {
		const folders = ['/f/a', '/f/b', '/f/c', '/f/d', '/f/e']
		const compiled: number[] = []
		/** Crashes on more than two folders, like tsc out of memory; reports an error in folder c. */
		const compile = (batch: readonly string[]): Compiled => {
			compiled.push(batch.length)
			if (batch.length > 2) return { outcome: 'crashed', output: '' }
			return batch.includes('/f/c')
				? { outcome: 'failed', output: '/f/c/probes.ts(1,1): error TS1: wrong' }
				: { outcome: 'passed', output: '' }
		}
		assert.deepEqual(typeCheck({ folders, compile }), ['/f/c'])
		assert.ok(compiled.every((size) => size <= 5))
	})
})
