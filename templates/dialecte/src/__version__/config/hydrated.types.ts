import type { Config } from './dialecte.config'
import type { __DIALECTE_NAME___EXTENSION_MODULES } from '@/__version__/extensions'
import type * as Core from '@dialecte/core'

type __DialecteName__Modules = typeof __DIALECTE_NAME___EXTENSION_MODULES
type __DialecteName__Extensions = Core.MergedExtensions<__DialecteName__Modules>

export namespace __DialecteName__ {
	export type Project<GenericCustomModules extends Core.ExtensionModules = Record<never, never>> =
		// A project takes the RAW modules and merges them itself when it opens a document.
		Core.Project<Config, __DialecteName__Modules & GenericCustomModules>
	export type Document = Core.Document<Config, __DialecteName__Extensions>

	export type ExtendedDocument<
		GenericCustomModules extends Core.ExtensionModules = Record<never, never>,
	> = Core.ExtendedDocument<Config, __DialecteName__Modules & GenericCustomModules>

	export type Context = Core.Context<Config>

	export type Query = Core.Query<Config> & Core.QueryExtensions<__DialecteName__Extensions>
	export type Transaction = Core.Transaction<Config> &
		Core.AllExtensions<__DialecteName__Extensions>
	export type TransactionHooks = Core.TransactionHooks<Config>

	// DEFINITION
	export type ElementsOf = Core.ElementsOf<Config>
	export type Ref<GenericElement extends ElementsOf> = Core.Ref<Config, GenericElement>
	/** The attributes of an element: by tag, or as declared under `GenericParent` when one is named. */
	export type AttributesValueObjectOf<
		GenericElement extends ElementsOf,
		GenericParent extends ElementsOf = never,
	> = Core.AttributesValueObjectOf<Config, GenericElement, GenericParent>
	export type AttributesOf<
		GenericElement extends ElementsOf,
		GenericParent extends ElementsOf = never,
	> = Core.AttributesOf<Config, GenericElement, GenericParent>
	export type FullAttributeObjectOf<GenericElement extends ElementsOf> = Core.FullAttributeObjectOf<
		Config,
		GenericElement
	>
	export type ChildrenOf<GenericElement extends ElementsOf> = Core.ChildrenOf<
		Config,
		GenericElement
	>
	export type ParentsOf<GenericElement extends ElementsOf> = Core.ParentsOf<Config, GenericElement>
	export type DescendantsOf<GenericElement extends ElementsOf> = Core.DescendantsOf<
		Config,
		GenericElement
	>
	export type AncestorsOf<GenericElement extends ElementsOf> = Core.AncestorsOf<
		Config,
		GenericElement
	>
	export type RootElementOf = Core.RootElementOf<Config>
	export type SingletonElementsOf = Core.SingletonElementsOf<Config>

	// OPERATIONS
	export type Operation = Core.Operation<Config>

	// RECORDS
	export type RawRecord<GenericElement extends ElementsOf> = Core.RawRecord<Config, GenericElement>
	export type TrackedRecord<GenericElement extends ElementsOf> = Core.TrackedRecord<
		Config,
		GenericElement
	>
	export type TreeRecord<GenericElement extends ElementsOf> = Core.TreeRecord<
		Config,
		GenericElement
	>

	export type ParentRelationship<GenericElement extends ElementsOf> = Core.ParentRelationship<
		Config,
		GenericElement
	>
	export type ChildRelationship<GenericElement extends ElementsOf> = Core.ChildRelationship<
		Config,
		GenericElement
	>

	export type Attribute<GenericElement extends ElementsOf> = Core.Attribute<Config, GenericElement>
	export type QualifiedAttribute<GenericElement extends ElementsOf> = Core.QualifiedAttribute<
		Config,
		GenericElement
	>

	// MISCELLANEOUS
	export type CloneMapping = Core.CloneMapping<Config>
}
