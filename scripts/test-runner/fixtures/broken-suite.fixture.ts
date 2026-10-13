// A suite whose describe callback throws while it is built: node --test prints it as failing and exits 0 (Node 24).
import { describe, it } from 'node:test'

describe('a suite built on a value that throws', () => {
	const value = (undefined as unknown as { field: string }).field
	it('never runs', () => {
		void value
	})
})
