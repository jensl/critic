import React, { useEffect, MouseEvent } from "react"

import {
  ElementToIDFunc,
  defineSelectionScope,
  resetSelectionScopeIf,
} from "../actions/uiSelectionScope"
import { useDispatch } from "../store"
import Registry from "."

type SelectorFunc = (ev: MouseEvent) => string | null

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
  useEffect(
    () => () => {
      dispatch(resetSelectionScopeIf(scopeID))
    },
    [dispatch, scopeID],
  )
  const onMouseDown = (event: MouseEvent) => {
    if (event.ctrlKey) return
    let useSelector
    if (typeof selector === "function") {
      useSelector = selector(event)
      if (useSelector === null) return
    } else useSelector = selector
    event.stopPropagation()
    event.preventDefault()
    const elements = [
      ...document.querySelectorAll<HTMLElement>(`#${scopeID} ${useSelector}`),
    ]
    dispatch(
      defineSelectionScope({
        event: event.nativeEvent,
        scopeID,
        elementType: "commit",
        elements,
        elementToID,
      }),
    )
  }
  return (
    <div className={className} id={scopeID} onMouseDown={onMouseDown}>
      {children}
    </div>
  )
}

export default Registry.add("Selection.Scope", SelectionScope)
