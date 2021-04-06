/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import React, { useContext, useEffect, useMemo, useRef, useState } from "react"

import { assertNotNull, assertTrue } from "../debug"

type ShortcutResult = {
  stopPropagation?: boolean
  preventDefault?: boolean
}

type ShortcutHandler =
  | { [key: string]: () => ShortcutResult | void }
  | ((ev: KeyboardEvent) => ShortcutResult | void)

class ShortcutScopeNode {
  children: ShortcutScopeNode[]

  constructor(readonly name: string, readonly handler: ShortcutHandler) {
    this.children = []
  }

  push(name: string, handler: ShortcutHandler) {
    const scope = new ShortcutScopeNode(name, handler)
    this.children.push(scope)
    return scope
  }

  pop(scope: ShortcutScopeNode) {
    assertTrue(this.children.includes(scope))
    this.children = this.children.filter((childScope) => childScope !== scope)
  }
}

function* traverse(root: ShortcutScopeNode): Iterable<ShortcutHandler> {
  const stack: [ShortcutScopeNode, number][] = [[root, 0]]

  while (stack.length) {
    const [node, childIndex] = stack.pop()!
    if (childIndex < node.children.length)
      stack.push([node, childIndex + 1], [node.children[childIndex], 0])
    else {
      yield node.handler
    }
  }
}

const ShortcutContext = React.createContext<ShortcutScopeNode | null>(null)

type Props<T> = {
  name: string
  handler: ShortcutHandler
  component?: string | React.ComponentClass<T> | React.FunctionComponent<T>
  componentProps?: T
}

export function ShortcutScope<T>({
  name,
  handler,
  children,
  component,
  componentProps,
}: React.PropsWithChildren<Props<T>>) {
  const parent = useContext(ShortcutContext)
  const [node, setNode] = useState<ShortcutScopeNode | null>(null)

  useEffect(() => {
    if (parent) {
      const node = parent.push(name, handler)
      setNode(node)
      return () => parent.pop(node)
    }
  }, [parent, handler])

  return React.createElement(
    component || "div",
    componentProps,
    node && (
      <ShortcutContext.Provider value={node}>
        {children}
      </ShortcutContext.Provider>
    ),
  )
}

const handleEvent = (ev: KeyboardEvent, root: ShortcutScopeNode) => {
  for (const handler of traverse(root)) {
    const result =
      typeof handler === "function" ? handler(ev) : handler[ev.key]?.()

    if (result) {
      if (result.preventDefault) ev.preventDefault()
      if (result.stopPropagation) {
        ev.stopPropagation()
        break
      }
    }
  }
  // const scopes = store.getState().ui.rest.keyboardShortcutScopes

  // const scopeType = ((parsedHash) => {
  //   switch (true) {
  //     case parsedHash.has("dialog"):
  //       return "dialog"
  //     case parsedHash.has("confirm"):
  //       return "confirm"
  //     case parsedHash.has("comment"):
  //     case parsedHash.has("issue"):
  //     case parsedHash.has("openIssue"):
  //     case parsedHash.has("resolvedIssue"):
  //     case parsedHash.has("addressedIssue"):
  //     case parsedHash.has("note"):
  //       return "comment"
  //     case parsedHash.has("tutorial"):
  //       return "tutorial"
  //     default:
  //       return "default"
  //   }
  // })(Hash.parse(location))

  // for (const scope of scopes) {
  //   if (scope.scopeType !== "all" && scope.scopeType !== scopeType) continue
  //   const result = scope.handler(event, store.dispatch, store.getState) || false
  //   if (result === true || result.preventDefault) event.preventDefault()
  // }
}

export const KeyboardEventHandler: React.FunctionComponent = ({ children }) => {
  const node = useMemo(() => new ShortcutScopeNode("<root>", {}), [])

  useEffect(() => {
    const handleKeyDown = (ev: KeyboardEvent) => {
      const { key, target } = ev

      assertNotNull(target)

      const { nodeName } = target as Node

      switch (key) {
        case "Escape":
          break

        case "ArrowUp":
        case "ArrowDown":
          if (nodeName === "TEXTAREA") return
          break

        case "ArrowLeft":
        case "ArrowRight":
          if (nodeName === "INPUT" || nodeName === "TEXTAREA") return
          break

        case "PageUp":
        case "PageDown":
          break

        default:
          return
      }

      handleEvent(ev, node)
    }

    const handleKeyPress = (ev: KeyboardEvent) => {
      const { ctrlKey, altKey, metaKey, target, key } = ev

      if (ctrlKey || altKey || metaKey) return

      assertNotNull(target)

      const { nodeName } = target as Node

      switch (nodeName) {
        case "INPUT":
          if (key === "Enter") {
            break
          }
          if (key === " ") {
            return
          }
          switch ((target as HTMLInputElement).type) {
            case "checkbox":
            case "radio":
              break

            default:
              return
          }
          break

        case "TEXTAREA":
          return

        default:
          break
      }

      handleEvent(ev, node)
    }

    document.addEventListener("keydown", handleKeyDown)
    document.addEventListener("keypress", handleKeyPress)

    return () => {
      document.removeEventListener("keydown", handleKeyDown)
      document.removeEventListener("keypress", handleKeyPress)
    }
  }, [document, node])

  return (
    <ShortcutContext.Provider value={node}>{children}</ShortcutContext.Provider>
  )
}
