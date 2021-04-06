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

import { onMouseDown } from "./uiMouse"
import { Dispatch, GetState, Thunk } from "../state"
import {
  BoundingRect,
  SET_SELECTION_SCOPE,
  SetSelectionScopeAction,
  SetSelectionRectAction,
  SET_SELECTION_RECT,
  ResetSelectionScopeAction,
  RESET_SELECTION_SCOPE,
  SET_SELECTED_ELEMENTS,
  SetSelectedElementsAction,
  SelectionElementType,
} from "."
import { identicalSets } from "../utils/Functions"
import { MouseMonitor } from "../utils/Mouse"

const setSelectionScope = (
  scopeID: string,
  elementType: SelectionElementType,
  elements: { [id: string]: HTMLElement },
  elementIDs: string[],
  boundingRect: BoundingRect,
): SetSelectionScopeAction => ({
  type: SET_SELECTION_SCOPE,
  scopeID,
  elementType,
  elements,
  elementIDs,
  boundingRect,
})

export const setSelectionRect = (
  boundingRect: BoundingRect,
): SetSelectionRectAction => ({
  type: SET_SELECTION_RECT,
  boundingRect,
})

export const setSelectedElements = (
  scopeID: string,
  selectedIDs: Set<string>,
  firstSelectedID: string | null,
  lastSelectedID: string | null,
  isPending: boolean = false,
  isRangeSelecting: boolean = false,
): SetSelectedElementsAction => ({
  type: SET_SELECTED_ELEMENTS,
  scopeID,
  selectedIDs,
  firstSelectedID,
  lastSelectedID,
  isPending,
  isRangeSelecting,
})

export const CLEAR_SELECTED_ELEMENTS = "CLEAR_SELECTED_ELEMENTS"
export const clearSelectedElements = () => ({ type: CLEAR_SELECTED_ELEMENTS })

const defaultElementToID = (el: HTMLElement) => el.id
const min = (values: number[]) => Math.min.apply(null, values)
const max = (values: number[]) => Math.max.apply(null, values)

export type ElementToIDFunc = (el: HTMLElement) => string

export type DefineSelectionScopeParams = {
  scopeID: string
  elementType: SelectionElementType
  elements: HTMLElement[]
  elementToID: ElementToIDFunc
}

export const defineSelectionScope = ({
  scopeID,
  elementType,
  elements,
  elementToID,
}: DefineSelectionScopeParams) => (
  dispatch: Dispatch,
  getState: GetState,
): MouseMonitor => {
  const elementIDs: string[] = []
  const elementsByID: { [id: string]: HTMLElement } = {}
  const allBoundingRects: BoundingRect[] = []

  elements.forEach((element) => {
    const elementID = elementToID!(element)
    elementIDs.push(elementID)
    elementsByID[elementID] = element
    allBoundingRects.push(element.getBoundingClientRect())
  })

  var top = min(allBoundingRects.map((rect) => rect.top))
  var right = max(allBoundingRects.map((rect) => rect.right))
  var bottom = max(allBoundingRects.map((rect) => rect.bottom))
  var left = min(allBoundingRects.map((rect) => rect.left))

  top += window.scrollY
  right += window.scrollX
  bottom += window.scrollY
  left += window.scrollX

  const boundingRect = {
    top,
    right,
    bottom,
    left,
  }

  if (getState().ui.selectionScope.scopeID === scopeID)
    dispatch(setSelectionRect(boundingRect))
  else {
    dispatch(
      setSelectionScope(
        scopeID,
        elementType,
        elementsByID,
        elementIDs,
        boundingRect,
      ),
    )
  }

  return ({ absoluteX, absoluteY, downAbsoluteX, downAbsoluteY, isDown }) => (
    dispatch: Dispatch,
    getState: GetState,
  ) => {
    const state = getState()
    const {
      scopeID,
      elements,
      elementIDs,
      selectedIDs: currentSelectedIDs,
      firstSelectedID: currentFirstSelectedID,
      lastSelectedID: currentLastSelectedID,
      isPending,
      isRangeSelecting,
      selectionAnchorID,
    } = state.ui.selectionScope

    if (scopeID === null) return null

    const width = Math.abs(absoluteX - downAbsoluteX)
    const height = Math.abs(absoluteY - downAbsoluteY)

    const newIsRangeSelecting = isRangeSelecting || width > 5 || height > 5

    // Current selection rectangle.
    const top = Math.min(absoluteY, downAbsoluteY) - window.scrollY
    const right = Math.max(absoluteX, downAbsoluteX) - window.scrollX
    const bottom = Math.max(absoluteY, downAbsoluteY) - window.scrollY
    const left = Math.min(absoluteX, downAbsoluteX) - window.scrollX

    var firstSelectedID = null
    var lastSelectedID = null
    const selectedIDs = new Set<string>()
    var inSelection = false

    for (const elementID of elementIDs) {
      const boundingRect = elements.get(elementID)!.getBoundingClientRect()
      const isInRange =
        top <= boundingRect.bottom &&
        boundingRect.top <= bottom &&
        left <= boundingRect.right &&
        boundingRect.left <= right
      var addToSelection = inSelection

      if (selectionAnchorID !== null && !newIsRangeSelecting) {
        if (elementID === selectionAnchorID || isInRange) {
          addToSelection = true
          if (elementID !== selectionAnchorID || !isInRange)
            inSelection = !inSelection
        }
      } else addToSelection = isInRange

      if (addToSelection) {
        if (firstSelectedID === null) firstSelectedID = elementID
        selectedIDs.add(elementID)
        lastSelectedID = elementID
      }
    }

    console.log({ isDown, newIsRangeSelecting })

    if (
      !isDown &&
      !newIsRangeSelecting &&
      selectedIDs.size === 1 &&
      state.ui.selectionScope.selectedIDs.size !== 0
    ) {
      dispatch({ type: "RESET_SELECTION_SCOPE" })
      return null
    }

    if (newIsRangeSelecting || selectedIDs.size > 1 || !isDown) {
      const newIsPending = isDown
      if (
        isPending !== newIsPending ||
        isRangeSelecting !== newIsRangeSelecting ||
        currentFirstSelectedID !== firstSelectedID ||
        currentLastSelectedID !== lastSelectedID ||
        !identicalSets(currentSelectedIDs, selectedIDs)
      ) {
        dispatch(
          setSelectedElements(
            scopeID,
            selectedIDs,
            firstSelectedID,
            lastSelectedID,
            newIsPending,
            newIsRangeSelecting,
          ),
        )
      }
    }

    return null
  }
}
