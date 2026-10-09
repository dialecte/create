/**
 * The error a user reads when the schema reader fails: the engine's own exception - its name without the module
 * path, and its whole message - without the Python traceback that leads to it (kept as the error's `cause`).
 * `hostPath` writes the engine's in-WebAssembly paths back as the user's.
 */
export function engineError(
	thrown: unknown,
	hostPath: (text: string) => string = (text) => text,
): Error {
	const message = thrown instanceof Error ? thrown.message : String(thrown)
	if (!message.includes('Traceback (most recent call last)')) {
		return thrown instanceof Error ? thrown : new Error(message)
	}
	// the exception starts at the first line after the last frame that is not indented
	const lines = message.trimEnd().split('\n')
	const lastFrame = lines.reduce(
		(last, line, index) => (line.startsWith('  File ') ? index : last),
		-1,
	)
	const start = lines.findIndex((line, index) => index > lastFrame && /^\S/.test(line))
	const exception = lines.slice(start === -1 ? -1 : start).join('\n')
	// `generate.errors.SchemaNotReadable: ...` -> `SchemaNotReadable: ...`
	return new Error(hostPath(exception.replace(/^[\w.]*\.(?=\w+:)/, '')), { cause: thrown })
}
