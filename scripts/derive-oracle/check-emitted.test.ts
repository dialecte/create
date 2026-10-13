import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { checkEmitted, emittedFiles } from './check-emitted.ts'

import type { DefinitionData, TypesData } from '../../src/derive/derive.types.ts'

// what the emitter writes for a definition, judged by the oracle - the path the corpus and fuzz tiers take
const FIXTURES = new URL('../../test/fixtures/definition/', import.meta.url)

describe('checkEmitted', () => {
	it('a schema declaring no element -> nothing written, nothing to judge', async () => {
		assert.deepEqual(await checkEmitted({ definition: {}, types: {} }), [])
	})

	it('a definition whose every element some other holds -> no root to write the constants for', async () => {
		const definition: DefinitionData = {
			A: {
				parents: ['B'],
				attributes: { sequence: [], details: {} },
				children: { sequence: ['B'], details: {} },
			},
			B: {
				parents: ['A'],
				attributes: { sequence: [], details: {} },
				children: { sequence: ['A'], details: {} },
			},
		}
		assert.deepEqual(await checkEmitted({ definition, types: {} }), [
			{ fact: 'root', element: '*', expected: [], emitted: undefined },
		])
	})

	it('every element held by another, one of them global -> the files written for it, no disagreement', async () => {
		/** A global element held by `other`, holding it in turn. */
		function held(other: string): DefinitionData[string] {
			return {
				parents: [other],
				global: true,
				attributes: { sequence: [], details: {} },
				children: { sequence: [other], details: {} },
			}
		}
		assert.deepEqual(
			await checkEmitted({ definition: { A: held('B'), B: held('A') }, types: {} }),
			[],
		)
	})

	for (const fixture of ['core-test', 'homonym', 'torture']) {
		it(`the constants emitted for ${fixture} -> no disagreement`, async () => {
			const { DEFINITION, TYPES } = (await import(
				new URL(`${fixture}/definition.generated.ts`, FIXTURES).href
			)) as {
				DEFINITION: DefinitionData
				TYPES: TypesData
			}
			assert.deepEqual(await checkEmitted({ definition: DEFINITION, types: TYPES }), [])
		})
	}

	it('a definition with a root -> the constants, the types and their probes', async () => {
		const { DEFINITION, TYPES } = (await import(
			new URL('torture/definition.generated.ts', FIXTURES).href
		)) as {
			DEFINITION: DefinitionData
			TYPES: TypesData
		}
		const files = emittedFiles({ definition: DEFINITION, types: TYPES })
		assert.deepEqual(Object.keys(files ?? {}), [
			'constants.generated.ts',
			'types.generated.ts',
			'probes.ts',
		])
	})
})
