import { describe, expect } from 'vitest'

import {
	ALL_XMLNS_NAMESPACES,
	CUSTOM_RECORD_ID_ATTRIBUTE,
	run__DialecteName__TestCases,
} from '@/__version__/test'

import type { HelloWorldGreeting } from './say-hello.types'
import type { __DialecteName__Test } from '@/__version__/test'

type TestCase = __DialecteName__Test.BaseXmlTestCase & { expected: HelloWorldGreeting }

// A read is tested with `withoutExport`: every row is imported into a fresh database, `act`
// asserts on what the query answers, and the runner cleans up. Nothing is written, so nothing
// is exported.
//
// `ns` declares the namespaces a test document needs, `id` gives a record a stable id you can
// name in a query.
describe('helloWorld.sayHello', () => {
	const ns = ALL_XMLNS_NAMESPACES
	const id = CUSTOM_RECORD_ID_ATTRIBUTE

	const testCases: __DialecteName__Test.TestCases<TestCase> = {
		'a __exampleRoot__ on its own → a document of one element': {
			sourceXml: /* xml */ `
				<__exampleRoot__ ${ns} ${id}="root">
					<!-- nothing in it -->
				</__exampleRoot__>
			`,
			expected: {
				message: 'Hello, world! This __exampleRoot__ document holds 1 element.',
				elementCount: 1,
				countByTagName: { __exampleRootKey__: 1 },
			},
		},
		// __ifExampleChild__

		'a __exampleRoot__ holding a __exampleChild__ → both are counted, each under its tag name': {
			sourceXml: /* xml */ `
				<__exampleRoot__ ${ns} ${id}="root">
					<__exampleChild__ ${id}="existing-child"__exampleChildAttributesXml__ />
				</__exampleRoot__>
			`,
			expected: {
				message: 'Hello, world! This __exampleRoot__ document holds 2 elements.',
				elementCount: 2,
				countByTagName: { __exampleRootKey__: 1, __exampleChildKey__: 1 },
			},
		},
		// __endIfExampleChild__
	}

	async function act({ testCase, source }: __DialecteName__Test.ActParams<TestCase>) {
		// a method of an extension is reached through its module: query.<module>.<method>
		const greeting = await source.query.helloWorld.sayHello()

		expect(greeting).toEqual(testCase.expected)
	}

	run__DialecteName__TestCases.withoutExport({ testCases, act })
})
