/** The part of StrykerJS's JSON report (mutation-testing-elements) the gate reads. */
export type MutationReport = {
	readonly files: Readonly<Record<string, ReportedFile>>
}

export type ReportedFile = {
	readonly source: string
	readonly mutants: readonly ReportedMutant[]
}

export type ReportedMutant = {
	readonly id: string
	readonly mutatorName: string
	readonly replacement?: string
	readonly status: string
	readonly location: { readonly start: Position; readonly end: Position }
}

/** 1-based line and column, as StrykerJS reports them. */
export type Position = { readonly line: number; readonly column: number }

/** A mutant no test noticed: where it is, what it changed, and its key in the record. */
export type Survivor = {
	readonly file: string
	readonly key: string
	readonly line: number
	readonly mutation: string
}

/** Per mutated file, the survivors accepted with the reason each cannot alter any output. */
export type SurvivorRecords = Readonly<Record<string, Readonly<Record<string, RecordedSurvivor>>>>

export type RecordedSurvivor = {
	readonly line: number
	readonly mutation: string
	/** Why no output can differ; empty until someone writes it - the gate refuses an empty reason. */
	readonly equivalent: string
}

export type Verdict = {
	readonly survivors: readonly Survivor[]
	/** Survivors the record does not list, or lists without a reason. */
	readonly unlisted: readonly Survivor[]
	/** Listed survivors of a mutated file that no longer survive. */
	readonly stale: readonly { readonly file: string; readonly key: string }[]
}
