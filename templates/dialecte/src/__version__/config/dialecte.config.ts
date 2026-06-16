import {
	DEFINITION,
	ELEMENT_NAMES,
	ATTRIBUTES,
	CHILDREN,
	PARENTS,
	DESCENDANTS,
	ANCESTORS,
	ROOT_ELEMENT,
	SINGLETON_ELEMENTS,
} from '../definition'
import { __DIALECTE_NAME___NAMESPACES } from './namespaces'

import type { IOConfig, AnyDialecteConfig, DatabaseConfig } from '@dialecte/core'

// __DialecteName__-specific IO configuration
export const __DIALECTE_NAME___IO_CONFIG = {
	supportedFileExtensions: ['.xml'],
} as const satisfies IOConfig

// __DialecteName__ database configuration
export const __DIALECTE_NAME___DATABASE_CONFIG = {
	recordSchema: {
		primaryKey: 'id',
		indexes: ['tagName', 'parent.id', 'parent.tagName'],
		compoundIndexes: [['id', 'tagName']],
		arrayIndexes: ['children.id', 'children.tagName'],
	},
} as const satisfies DatabaseConfig

export { __DIALECTE_NAME___NAMESPACES }

export const __DIALECTE_NAME___DIALECTE_CONFIG = {
	singletonElements: SINGLETON_ELEMENTS,
	elements: ELEMENT_NAMES,
	namespaces: __DIALECTE_NAME___NAMESPACES,
	attributes: ATTRIBUTES,
	children: CHILDREN,
	parents: PARENTS,
	descendants: DESCENDANTS,
	ancestors: ANCESTORS,
	database: __DIALECTE_NAME___DATABASE_CONFIG,
	io: __DIALECTE_NAME___IO_CONFIG,
	definition: DEFINITION,
	rootElementName: ROOT_ELEMENT,
} as const satisfies AnyDialecteConfig

export type Config = Readonly<typeof __DIALECTE_NAME___DIALECTE_CONFIG>
