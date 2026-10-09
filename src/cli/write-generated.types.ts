import type { DefinitionData, TypesData } from '../derive/derive.types.ts'

/** What the engine hands back for a schema: the definition, its types, and the TypeScript source of both. */
export type GeneratedDefinition = {
	readonly definition: DefinitionData
	readonly types: TypesData
	readonly source: string
}
