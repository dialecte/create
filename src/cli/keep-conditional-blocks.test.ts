import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { keepConditionalBlocks } from './keep-conditional-blocks.ts'

type TestCase = {
	description: string
	lines: string[]
	hasChild: boolean
	expected: string[] | RegExp
}

const BOTH_BLOCKS = [
	'before',
	'<!-- __ifExampleChild__ -->',
	'child line',
	'<!-- __endIfExampleChild__ -->',
	'\t// __ifNoExampleChild__',
	'no-child line',
	'\t// __endIfNoExampleChild__',
	' * __ifExampleChild__',
	' * child doc line',
	' * __endIfExampleChild__',
	'after',
]

const TEST_CASES: TestCase[] = [
	{
		description:
			'a root with a child -> the child blocks kept, the no-child block dropped, markers gone',
		lines: BOTH_BLOCKS,
		hasChild: true,
		expected: ['before', 'child line', ' * child doc line', 'after'],
	},
	{
		description:
			'a root without child -> the child blocks dropped, the no-child block kept, markers gone',
		lines: BOTH_BLOCKS,
		hasChild: false,
		expected: ['before', 'no-child line', 'after'],
	},
	{
		description: 'a block opened inside another -> throws',
		lines: [
			'// __ifExampleChild__',
			'// __ifNoExampleChild__',
			'inner',
			'// __endIfNoExampleChild__',
			'// __endIfExampleChild__',
		],
		hasChild: true,
		expected: /template\.md:2: __ifNoExampleChild__ opens inside __ifExampleChild__/,
	},
	{
		description: 'a block never closed -> throws',
		lines: ['// __ifExampleChild__', 'child line', 'after'],
		hasChild: true,
		expected: /template\.md: __ifExampleChild__ opened on line 1 is never closed/,
	},
	{
		description: 'an end with no block open -> throws',
		lines: ['before', '// __endIfExampleChild__', 'after'],
		hasChild: true,
		expected: /template\.md:2: __endIfExampleChild__ closes no open block/,
	},
	{
		description: 'an end of the other kind -> throws',
		lines: ['// __ifExampleChild__', 'child line', '// __endIfNoExampleChild__'],
		hasChild: false,
		expected: /template\.md:3: __endIfNoExampleChild__ closes __ifExampleChild__/,
	},
	{
		description: 'a marker inside a content line -> throws',
		lines: ['const x = 1 // __ifExampleChild__', 'child line', '// __endIfExampleChild__'],
		hasChild: true,
		expected: /template\.md:1: __ifExampleChild__ must be alone on its line/,
	},
]

describe('keepConditionalBlocks', () => {
	for (const { description, lines, hasChild, expected } of TEST_CASES) {
		it(description, () => {
			const params = { text: lines.join('\n'), hasChild, source: 'template.md' }
			if (expected instanceof RegExp) {
				assert.throws(() => keepConditionalBlocks(params), expected)
			} else assert.equal(keepConditionalBlocks(params), expected.join('\n'))
		})
	}
})
