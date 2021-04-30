import React, { ComponentType } from "react"

import { assertFalse, assertNotNull } from "../debug"
import { baseComponents } from "../reducers/uiRegistry"
import { useSelector } from "../store"

function add<T extends ComponentType<any>>(key: string, Component: T): T {
  assertFalse(
    baseComponents.hasOwnProperty(key),
    `Duplicate registry key: ${key}`,
  )
  baseComponents[key] = Component
  return ((props) => {
    const registry = useSelector((state) => state.ui.registry)
    const component = registry.get(key)
    if (component) {
      const { override } = component
      if (override?.callback) {
        const { callback: Override } = override
        return <Override {...props} BaseComponent={Component} />
      }
    }
    return <Component {...props} />
  }) as T
}

const Registry = { add }

export default Registry
