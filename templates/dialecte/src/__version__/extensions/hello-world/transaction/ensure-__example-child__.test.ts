import { describe } from 'vitest'

import {
	ALL_XMLNS_NAMESPACES,
	CUSTOM_RECORD_ID_ATTRIBUTE,
	run__DialecteName__TestCases,
} from '@/__version__/test'

import type { __DialecteName__Test } from '@/__version__/test'

type TestCase = __DialecteName__Test.BaseXmlTestCase

// A write is tested with `withExport`: XML in, XPath out. Every row is imported, `act` runs the
// transaction, the document is exported again and each query of the row is checked against it.
// Comment the element that is missing in `sourceXml`, so the gap the transaction fills is visible;
// pair an `unexpectedQueries` entry with what must NOT have appeared. `ns` declares the namespaces
// a test document needs; `id` gives a record a stable, telling id.
//
// An XPath step names an element of the default namespace `default:Name`, and one of no namespace
// by its bare name.
describe('helloWorld.ensure__ExampleChild__', () => {
	const ns = ALL_XMLNS_NAMESPACES
	const id = CUSTOM_RECORD_ID_ATTRIBUTE

	const testCases: __DialecteName__Test.TestCases<TestCase> = {
		'a __exampleRoot__ without __exampleChild__ → one is added': {
			sourceXml: /* xml */ `
				<__exampleRoot__ ${ns} ${id}="root">
					<!-- no __exampleChild__ -->
				</__exampleRoot__>
			`,
			expectedQueries: ['__exampleChildXPath__'],
		},

		'a __exampleRoot__ already holding a __exampleChild__ → it is kept, no second one is added': {
			sourceXml: /* xml */ `
				<__exampleRoot__ ${ns} ${id}="root">
					<__exampleChild__ ${id}="existing-child"__exampleChildAttributesXml__ />
				</__exampleRoot__>
			`,
			expectedQueries: ['__exampleChildXPath__'],
			// an unexpected query must match up to its last step: the first is there, a second is not
			unexpectedQueries: ['__exampleChildXPath__[2]'],
		},
	}

	async function act({
		source,
	}: __DialecteName__Test.ActParams<TestCase>): Promise<__DialecteName__Test.ActResult> {
		// every write happens in a transaction: all of it is committed, or none of it
		await source.transaction(async (tx) => {
			await tx.helloWorld.ensure__ExampleChild__()
		})

		return { assertOn: 'source' }
	}

	run__DialecteName__TestCases.withExport({ testCases, act })
})
