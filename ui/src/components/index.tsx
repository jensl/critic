import React, { ComponentType } from "react"

import { assertFalse, assertNotNull } from "../debug"
import { baseComponents } from "../reducers/uiRegistry"
import { useSelector } from "../store"

function add<T extends ComponentType<any>>(key: string, component: T): T {
  assertFalse(
    baseComponents.hasOwnProperty(key),
    `Duplicate registry key: ${key}`,
  )
  baseComponents[key] = component
  return (({ ...props }) => {
    const registry = useSelector((state) => state.ui.registry)
    const component = registry.get(key)
    assertNotNull(component, key)
    const { base: Base, override } = component
    if (override?.callback) {
      const { callback: Override } = override
      return <Override {...props} BaseComponent={component.base} />
    }
    return <Base {...props} />
  }) as T
}

const Registry = { add }

export default Registry
