import { XMLNS_XSI_NAMESPACE } from '@dialecte/core/helpers'
import { XMLNS_DEV_NAMESPACE } from '@dialecte/core/test'

import { __DIALECTE_NAME___DIALECTE_CONFIG } from '@/__version__/config'

/** The default namespace of this dialecte, as an attribute of a fixture's root. */
export const XMLNS___DIALECTE_NAME___NAMESPACE = `xmlns="${__DIALECTE_NAME___DIALECTE_CONFIG.namespaces.default.uri}"`
/** Every namespace a fixture's root declares: this dialecte's, the test record ids and xsi. */
export const ALL_XMLNS_NAMESPACES = `${XMLNS___DIALECTE_NAME___NAMESPACE} ${XMLNS_DEV_NAMESPACE} ${XMLNS_XSI_NAMESPACE}`
