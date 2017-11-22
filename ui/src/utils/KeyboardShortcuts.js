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

import React from "react"

import store from "../store"
import {
  pushKeyboardShortcutScope,
  popKeyboardShortcutScope,
} from "../actions/ui"
import Hash from "./Hash"

const handleEvent = ({ event, location, history }) => {
  const scopes = store.getState().ui.rest.keyboardShortcutScopes

  const scopeType = ((parsedHash) => {
    switch (true) {
      case parsedHash.has("dialog"):
        return "dialog"
      case parsedHash.has("confirm"):
        return "confirm"
      case parsedHash.has("comment"):
      case parsedHash.has("issue"):
      case parsedHash.has("openIssue"):
      case parsedHash.has("resolvedIssue"):
      case parsedHash.has("addressedIssue"):
      case parsedHash.has("note"):
        return "comment"
      case parsedHash.has("tutorial"):
        return "tutorial"
      default:
        return "default"
    }
  })(Hash.parse(location))

  for (const scope of scopes) {
    if (scope.scopeType !== "all" && scope.scopeType !== scopeType) continue
    const result = scope.handler(event, store.dispatch, store.getState) || false
    if (result === true || result.preventDefault) event.preventDefault()
  }
}

export const handleKeyDown = ({ event, ...args }) => {
  const { nodeName } = event.target

  switch (event.key) {
    case "Escape":
      break

    case "ArrowUp":
    case "ArrowDown":
      if (nodeName === "TEXTAREA") return
      break

    case "ArrowLeft":
    case "ArrowRight":
      if (["INPUT", "TEXTAREA"].includes(nodeName)) return
      break

    case "PageUp":
    case "PageDown":
      break

    default:
      return
  }

  handleEvent({ event, ...args })
}

export const handleKeyPress = ({ event, ...args }) => {
  if (event.ctrlKey || event.altKey || event.metaKey) {
    return
  }

  switch (event.target.nodeName) {
    case "INPUT":
      if (event.key === "Enter") {
        break
      }
      if (event.which === 32) {
        return
      }
      switch (event.target.type) {
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

  handleEvent({ event, ...args })
}

export const withKeyboardShortcuts = (
  name,
  handlers,
  { scopeType = "default" } = {}
) => (WrappedComponent) => {
  var handler
  if (typeof handlers === "function") {
    handler = handlers
  } else {
    handler = (event, props) => {
      var handler
      if (handlers.hasOwnProperty(event.key)) handler = handlers[event.key]
      else if (handlers.hasOwnProperty(event.code))
        handler = handlers[event.code]
      else return false
      const result = handler(props, event)
      return result !== undefined ? result : false
    }
  }
  return class extends React.Component {
    componentDidMount() {
      this.token = store.dispatch(
        pushKeyboardShortcutScope({
          name,
          handler: (event) => handler(event, this.props),
          scopeType,
        })
      )
    }

    componentWillUnmount() {
      store.dispatch(popKeyboardShortcutScope(this.token))
    }

    render() {
      return <WrappedComponent {...this.props} />
    }
  }
}

export const blockKeyboardShortcuts = withKeyboardShortcuts("block", () => ({
  stopPropagation: true,
}))

export const BlockKeyboardShortcuts = blockKeyboardShortcuts((props) => (
  <React.Fragment>{props.children}</React.Fragment>
))

export default withKeyboardShortcuts
