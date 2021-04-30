import React, { useEffect, MouseEvent } from "react"

import Registry from "."
import {
  ElementToIDFunc,
  defineSelectionScope,
  SelectorFunc,
} from "../actions/uiSelectionScope"
import { useDispatch } from "../store"
import { ShortcutScope } from "../utils/KeyboardShortcuts"
import { useMouseTracker } from "../utils/Mouse"

type Props = {
  className?: string
  scopeID: string
  elementToID: ElementToIDFunc
  selector?: string | SelectorFunc
}

const SelectionScope: React.FunctionComponent<Props> = ({
  className,
  scopeID,
  elementToID,
  selector = "> *",
  children,
}) => {
  const dispatch = useDispatch()
  const startMouseTracking = useMouseTracker()
  useEffect(
    () => () => {
      dispatch({ type: "RESET_SELECTION_SCOPE", scopeID })
    },
    [dispatch, scopeID],
  )
  const useSelector: SelectorFunc = (anchor, focus) => {
    let useSelector
    if (typeof selector === "function") {
      useSelector = selector(anchor, focus)
      if (useSelector === null) return null
    } else useSelector = selector
    return `#${scopeID} ${useSelector}`
  }
  const onMouseDown = (event: MouseEvent) => {
    if (event.ctrlKey) return
    const monitor = dispatch(
      defineSelectionScope({
        scopeID,
        elementType: "commit",
        elementToID,
        selector: useSelector,
        anchor: event.target as HTMLElement,
      }),
    )
    if (monitor) {
      event.stopPropagation()
      event.preventDefault()
      startMouseTracking(event.nativeEvent, monitor)
    }
  }
  return (
    <ShortcutScope
      name={`SelectionScope:${scopeID}`}
      handler={{
        Escape: () => void dispatch({ type: "RESET_SELECTION_SCOPE", scopeID }),
      }}
      componentProps={{
        className,
        id: scopeID,
        onMouseDown,
      }}
    >
      {children}
    </ShortcutScope>
  )
}

export default Registry.add("Selection.Scope", SelectionScope)
