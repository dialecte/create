import type { Config } from '@/__version__/config'
import type * as Core from '@dialecte/core'

/**
 * The smallest useful write: make sure the __exampleRoot__ holds a __exampleChild__. `ensureChild` is
 * get-or-create: a __exampleChild__ already there with these attributes is handed back as it is, so
 * running this twice never adds a second one.
 *
 * `ensureChild` checks what you write against the definition as you type: `tagName` must be a
 * child the __exampleRoot__ allows, and `attributes` is mandatory exactly when that child requires
 * one - each value here is one the schema accepts.
 */
export async function ensure__ExampleChild__(tx: Core.Transaction<Config>) {
	// a read inside a transaction sees what the transaction has staged so far
	const root = await tx.getRoot()

	return tx.ensureChild(root, {
		tagName: '__exampleChild__' /* __exampleChildAttributesArgument__ */,
	})
}
