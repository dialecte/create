/** Where a dialecte keeps its generated definition: its package root and the definition's folder in it. */
export type DialecteLocation = { readonly packageRoot: string; readonly folder: string }

/** The root a proof run uses, and how it was obtained. */
export type ProofRoot = { readonly tag: string; readonly note: string }
