/** What one `tsc` run over a batch of folders gives: its verdict, and its diagnostics to place in the folders. */
export type Compiled = {
	readonly outcome: 'passed' | 'failed' | 'crashed'
	readonly output: string
}

/** Type-checks a batch of folders: `tsc --strict` by default, a stand-in in tests. */
export type Compile = (folders: readonly string[]) => Compiled
