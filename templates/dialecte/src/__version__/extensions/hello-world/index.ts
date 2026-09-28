import * as helloWorldQueries from './query'
// __ifExampleChild__
import * as helloWorldTransactions from './transaction'
// __endIfExampleChild__

/**
 * A small extension showing what a dialecte can be taught, written with the elements of this
 * package's schema. Copy the shape, then delete this folder and its line in `../index.ts`.
 *
 * - `query/`: reads. `sayHello` counts what a document is made of.
 * __ifExampleChild__
 * - `transaction/`: writes. `ensure__ExampleChild__` gives the __exampleRoot__ a __exampleChild__, once,
 *   with every attribute a __exampleChild__ requires.
 * __endIfExampleChild__
 * - the test next to each is table-driven, one row per behavior, written with the runners of
 *   `@/__version__/test`: `withoutExport` for a read, `withExport` for a write checked as XML with
 *   XPath (`generic` exists for a pure function).
 *
 * A method is a plain function whose FIRST parameter is the query (or the transaction). That
 * parameter is dropped when the module is registered, so from a document it reads
 * `doc.query.helloWorld.sayHello()` and, inside a transaction, `tx.helloWorld.<method>()`.
 *
 * To add one: write the test first, next to the function; export the function from its folder's
 * `index.ts`. Type its first parameter `Core.Query<Config>` or `Core.Transaction<Config>`, never the
 * hydrated `__DialecteName__.Query`: that type is built from the extensions themselves, and using it
 * inside one makes a cycle. A method calls a sibling by importing it and handing over its own `query`.
 */
export const helloWorld = {
	query: helloWorldQueries,
	// __ifExampleChild__
	transaction: helloWorldTransactions,
	// __endIfExampleChild__
}
