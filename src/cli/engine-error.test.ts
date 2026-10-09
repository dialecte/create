import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { engineError } from './engine-error.ts'

const traceback = (...exception: string[]) =>
	new Error(
		[
			'Traceback (most recent call last):',
			'  File "/lib/python312.zip/_pyodide/_base.py", line 574, in eval_code_async',
			'    await CodeRunner(',
			...exception,
			'',
		].join('\n'),
	)

describe('engineError', () => {
	it('a Python traceback -> the exception, its module left out, the traceback as the cause', () => {
		const thrown = traceback(
			"generate.errors.SchemaNotReadable: /in/entry.xsd: No such file: '/base.xsd'",
		)
		const error = engineError(thrown)
		assert.equal(error.message, "SchemaNotReadable: /in/entry.xsd: No such file: '/base.xsd'")
		assert.equal(error.cause, thrown)
	})

	it('an exception written on several lines -> all of them, its paths written back as the host has them', () => {
		const thrown = traceback(
			"xmlschema.validators.exceptions.XMLSchemaParseError: 'x' is not an element of the schema:",
			'',
			'Schema URL: file:///in/home/me/x.xsd',
		)
		const error = engineError(thrown, (text) => text.replaceAll('/in/', '/'))
		assert.equal(
			error.message,
			"XMLSchemaParseError: 'x' is not an element of the schema:\n\nSchema URL: file:///home/me/x.xsd",
		)
	})

	it('any other error -> itself', () => {
		const thrown = new Error('No vendored wheels found')
		assert.equal(engineError(thrown), thrown)
	})
})
