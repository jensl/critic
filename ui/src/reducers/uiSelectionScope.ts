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

import { castImmutable, immerable } from "immer"

import {
  DOCUMENT_CLICKED,
  SET_SELECTION_SCOPE,
  RESET_SELECTION_SCOPE,
  SET_SELECTION_RECT,
  SET_SELECTED_ELEMENTS,
  BoundingRect,
  SelectionElementType,
  SelectionElementID,
  SelectionScopeID,
} from "../actions"
import produce from "./immer"

type ScopeID = SelectionScopeID
type ElementID = SelectionElementID

type SelectionScopeProps = {
  elementType: SelectionElementType | null
  scopeID: ScopeID | null
  elements: ReadonlyMap<ElementID, HTMLElement>
  elementIDs: readonly ElementID[]
  selectionAnchorID: ElementID | null
  firstSelectedID: ElementID | null
  lastSelectedID: ElementID | null
  selectedIDs: ReadonlySet<ElementID>
  boundingRect: BoundingRect | null
  isPending: boolean
  isRangeSelecting: boolean
}

class _SelectionScope {
  [immerable] = true

  elementType: SelectionElementType | null = null
  scopeID: ScopeID | null = null
  elements: Map<ElementID, HTMLElement> = new Map()
  elementIDs: ElementID[] = []
  selectionAnchorID: ElementID | null = null
  firstSelectedID: ElementID | null = null
  lastSelectedID: ElementID | null = null
  selectedIDs: Set<ElementID> = new Set()
  boundingRect: BoundingRect | null = null
  isPending: boolean = false
  isRangeSelecting: boolean = false

  reset() {
    this.elementType = null
    this.scopeID = null
    this.elements = new Map()
    this.elementIDs = []
    this.selectionAnchorID = null
    this.firstSelectedID = null
    this.lastSelectedID = null
    this.selectedIDs = new Set()
    this.boundingRect = null
    this.isPending = false
    this.isRangeSelecting = false
  }

  update(updates: Partial<SelectionScopeProps>) {
    Object.assign(this, updates)
  }
}

export const selectionScope = produce<_SelectionScope>((draft, action) => {
  switch (action.type) {
    case SET_SELECTION_SCOPE:
      draft.update({
        ...action,
        elements: new Map<ElementID, HTMLElement>(
          Object.entries(action.elements),
        ),
      })
      break

    case RESET_SELECTION_SCOPE:
    case DOCUMENT_CLICKED:
      draft.reset()
      break

    case SET_SELECTION_RECT:
      draft.boundingRect = action.boundingRect
      break

    case SET_SELECTED_ELEMENTS:
      draft.update({
        firstSelectedID: action.firstSelectedID,
        selectedIDs: new Set(action.selectedIDs),
        lastSelectedID: action.lastSelectedID,
        isPending: action.isPending,
        isRangeSelecting: action.isRangeSelecting && action.isPending,
      })
      if (action.isRangeSelecting) draft.selectionAnchorID = null
      else if (action.selectedIDs.size === 1 && !action.isPending)
        draft.selectionAnchorID = action.firstSelectedID
      break
  }
}, castImmutable(new _SelectionScope()))

export type SelectionScope = ReturnType<typeof selectionScope>
