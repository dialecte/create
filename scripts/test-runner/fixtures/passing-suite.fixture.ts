import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

describe('a passing suite', () => {
	it('passes', () => {
		assert.equal(1, 1)
	})
})
