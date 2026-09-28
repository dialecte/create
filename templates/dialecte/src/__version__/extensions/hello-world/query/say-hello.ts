import type { HelloWorldGreeting } from './say-hello.types'
import type { Config } from '@/__version__/config'
import type * as Core from '@dialecte/core'

/**
 * The smallest useful read: what is this document made of?
 *
 * `findDescendants` answers with the records of a subtree grouped by tag name. It knows from the
 * definition which tag names can occur under an element, so no tree is walked by hand.
 */
export async function sayHello(query: Core.Query<Config>): Promise<HelloWorldGreeting> {
	const root = await query.getRoot()
	const descendantsByTagName = await query.findDescendants(root)

	const countByTagName: HelloWorldGreeting['countByTagName'] = { [root.tagName]: 1 }
	// typed for its length only: a root that allows no child has no descendant tag to name
	for (const [tagName, records] of Object.entries<readonly unknown[]>(descendantsByTagName)) {
		if (records.length > 0) countByTagName[tagName] = records.length
	}
	const elementCount = Object.values(countByTagName).reduce((total, count) => total + count, 0)
	const counted = elementCount === 1 ? '1 element' : `${elementCount} elements`

	return {
		message: `Hello, world! This ${root.tagName} document holds ${counted}.`,
		elementCount,
		countByTagName,
	}
}
