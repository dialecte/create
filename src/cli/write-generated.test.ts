import assert from 'node:assert/strict'
import { mkdtempSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, it } from 'node:test'

import { writeGenerated } from './write-generated.ts'

import type { GeneratedDefinition } from './write-generated.types.ts'

const namespace = { prefix: '', uri: 'urn:t' }
const nothing = { sequence: [], details: {} }
const twoRoots: GeneratedDefinition = {
	definition: {
		First: { namespace, parents: [], attributes: nothing, children: nothing },
		Second: { namespace, parents: [], attributes: nothing, children: nothing },
	},
	types: {},
	source: '// the definition\n',
}

describe('writeGenerated', () => {
	it('a root decided -> the three files, and the facts of the example', async () => {
		const outDir = mkdtempSync(join(tmpdir(), 'write-generated-'))
		const facts = await writeGenerated({ outDir, generated: twoRoots, root: 'Second' })
		assert.deepEqual(readdirSync(outDir).sort(), [
			'constants.generated.ts',
			'definition.generated.ts',
			'types.generated.ts',
		])
		assert.equal(readFileSync(join(outDir, 'definition.generated.ts'), 'utf-8'), twoRoots.source)
		assert.ok(
			readFileSync(join(outDir, 'constants.generated.ts'), 'utf-8').includes(
				"ROOT_ELEMENT = 'Second'",
			),
		)
		assert.deepEqual(facts, { root: { name: 'Second', namespaceUri: 'urn:t' }, child: null })
	})

	it('a root left undecided -> refused, naming --root, and the folder left as it was', async () => {
		const outDir = mkdtempSync(join(tmpdir(), 'write-generated-'))
		writeFileSync(join(outDir, 'definition.generated.ts'), 'previous')
		await assert.rejects(writeGenerated({ outDir, generated: twoRoots }), /--root/)
		assert.deepEqual(readdirSync(outDir), ['definition.generated.ts'])
		assert.equal(readFileSync(join(outDir, 'definition.generated.ts'), 'utf-8'), 'previous')
	})
})
