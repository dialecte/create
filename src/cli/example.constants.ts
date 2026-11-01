// Lines between these markers exist only when the root allows a child (or, for the `No` pair, only
// when it allows none); the marker lines themselves are dropped.
export const IF_CHILD = '__ifExampleChild__'
export const END_IF_CHILD = '__endIfExampleChild__'
export const IF_NO_CHILD = '__ifNoExampleChild__'
export const END_IF_NO_CHILD = '__endIfNoExampleChild__'

/** Each opening marker and the one that closes its block. Blocks do not nest. */
export const BLOCK_END_OF: Readonly<Record<string, string>> = {
	[IF_CHILD]: END_IF_CHILD,
	[IF_NO_CHILD]: END_IF_NO_CHILD,
}

/** The comment a marker line may wear: `// x`, ` * x` (inside a doc comment) or `<!-- x -->`. */
export const MARKER_COMMENT_OPEN = /^(?:\/\/|\*|<!--)\s*/
export const MARKER_COMMENT_CLOSE = /\s*-->$/
