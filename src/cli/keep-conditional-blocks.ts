import {
	BLOCK_END_OF,
	END_IF_CHILD,
	END_IF_NO_CHILD,
	IF_CHILD,
	IF_NO_CHILD,
	MARKER_COMMENT_CLOSE,
	MARKER_COMMENT_OPEN,
} from './example.constants.ts'

import type { OpenBlock } from './keep-conditional-blocks.types.ts'

/**
 * Keep the lines of a template that apply to the schema: a child block when the root allows a child, a no-child
 * block when it allows none; the marker lines go. A marker stands alone on its line (a comment around it is
 * fine), blocks do not nest and every block is closed: anything else throws, naming the file and the line.
 */
export function keepConditionalBlocks(params: {
	text: string
	hasChild: boolean
	/** The file the text comes from, named in the errors. */
	source: string
}): string {
	const { text, hasChild, source } = params
	const kept: string[] = []
	let open: OpenBlock | undefined
	for (const [index, line] of text.split('\n').entries()) {
		const lineNumber = index + 1
		const marker = markerOf({ line, location: `${source}:${lineNumber}` })
		if (marker === undefined) {
			if (open === undefined || (open.marker === IF_CHILD) === hasChild) kept.push(line)
		} else if (marker in BLOCK_END_OF) {
			if (open !== undefined) {
				throw new Error(`${source}:${lineNumber}: ${marker} opens inside ${open.marker}`)
			}
			open = { marker, lineNumber }
		} else {
			if (open === undefined) {
				throw new Error(`${source}:${lineNumber}: ${marker} closes no open block`)
			}
			if (BLOCK_END_OF[open.marker] !== marker) {
				throw new Error(`${source}:${lineNumber}: ${marker} closes ${open.marker}`)
			}
			open = undefined
		}
	}
	if (open !== undefined) {
		throw new Error(`${source}: ${open.marker} opened on line ${open.lineNumber} is never closed`)
	}
	return kept.join('\n')
}

/** The marker a line holds, if any; a marker sharing its line with content throws. */
function markerOf(params: { line: string; location: string }): string | undefined {
	const { line, location } = params
	const marker = [IF_CHILD, END_IF_CHILD, IF_NO_CHILD, END_IF_NO_CHILD].find((candidate) =>
		line.includes(candidate),
	)
	if (marker === undefined) return undefined
	const bare = line.trim().replace(MARKER_COMMENT_OPEN, '').replace(MARKER_COMMENT_CLOSE, '')
	if (bare !== marker) throw new Error(`${location}: ${marker} must be alone on its line`)
	return marker
}
