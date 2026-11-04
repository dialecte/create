import { join } from 'node:path'

/** A project's own oxfmt, from its folder. */
export const OXFMT_BIN = join('node_modules', '.bin', 'oxfmt')

/** The files whose presence says a project configured its formatter. */
export const OXFMT_CONFIGS = ['.oxfmtrc.json', '.oxfmtrc.jsonc']
