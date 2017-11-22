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

import { generateLinkPath } from "../utils/Changeset"
import { setSelectedElements, defineSelectionScope } from "./uiSelectionScope"

export const SET_ACTIONS_IN_VIEW = "SET_ACTIONS_IN_VIEW"
export const setActionsInView = (value) => ({
  type: SET_ACTIONS_IN_VIEW,
  value,
})

export const SET_DO_DIRECTLY = "SET_DO_DIRECTLY"
export const setDoDirectly = (value) => ({
  type: SET_DO_DIRECTLY,
  value,
})

export const SET_SHOW_ALL = "COMMIT_LIST_SET_SHOW_ALL"
export const setShowAll = (value) => ({
  type: SET_SHOW_ALL,
  value,
})

export const reviewSelectedCommits = ({
  location,
  history,
  match,
  review,
  repository,
}) => (dispatch, getState) => {
  const state = getState()
  const { commits } = state.resource
  const { selectionScope } = state.ui
  const { firstSelectedID, lastSelectedID } = selectionScope
  const params = { location, history, match, review, repository }

  if (firstSelectedID === lastSelectedID) {
    params.singleCommit = commits.byID.get(firstSelectedID)
  } else {
    const firstCommit = commits.byID.get(lastSelectedID)
    params.fromCommit = firstCommit.sha1 + "^"
    params.toCommit = commits.byID.get(firstSelectedID)
  }

  history.push(generateLinkPath(params))
}

const getPartitionIndex = (review, partition) =>
  review.partitions.indexOf(partition)

const firstPartitionWithCommits = (review) => {
  for (const partition of review.partitions) {
    if (partition.commits.size) {
      return partition
    }
  }
  return null
}

export const selectNextCommit = ({ review, additive, selectionKey = null }) => (
  dispatch,
  getState
) => {
  const state = getState()
  const {
    scopeID,
    firstSelectedID,
    lastSelectedID,
    selectedIDs,
    elementIDs,
  } = state.ui.selectionScope

  var currentCommitID = null
  var partition = null

  if (scopeID !== null) {
    let [key, partitionIndex] = scopeID.split(":")
    if (key === "commits") {
      partitionIndex = parseInt(partitionIndex, 10)
      partition = review.partitions.get(partitionIndex)
      currentCommitID = lastSelectedID
    }
  }

  var nextScopeID = scopeID
  var selector = null
  var nextCommitID = null
  var nextFirstSelectedID = additive ? firstSelectedID : null
  var nextSelectedIDs = new Set(additive ? selectedIDs : [])

  if (currentCommitID !== null) {
    const currentCommitIndex = elementIDs.indexOf(currentCommitID)
    if (currentCommitIndex < elementIDs.length - 1) {
      nextCommitID = elementIDs[currentCommitIndex + 1]
    } else {
      if (additive) {
        return
      }
      nextScopeID = null
      if (selectionKey === null) {
        let partitionIndex = getPartitionIndex(review, partition)
        if (partitionIndex < review.partitions.size - 1) {
          ++partitionIndex
          nextScopeID = `commits:${partitionIndex}`
          selector = `.partition${partitionIndex}`
          nextCommitID = review.partitions.get(partitionIndex).commits.first()
        }
      }
    }
  }

  if (nextScopeID === null) {
    if (selectionKey === null) {
      const partition = firstPartitionWithCommits(review)
      const partitionIndex = getPartitionIndex(review, partition)
      nextScopeID = `commits:${partitionIndex}`
      selector = `.partition${partitionIndex}`
      nextCommitID = partition.commits.first()
    } else {
      nextScopeID = "commits:0"
      selector = "." + selectionKey
      nextCommitID = null
    }
  }

  if (nextScopeID !== scopeID) {
    const elements = document.querySelectorAll(selector)
    dispatch(
      defineSelectionScope(nextScopeID, elements, (element) =>
        parseInt(element.dataset.commitId, 10)
      )
    )
    if (nextCommitID === null && elements.length) {
      nextCommitID = parseInt(elements[0].dataset.commitId, 10)
    }
  } else if (nextCommitID === null) {
    nextCommitID = elementIDs[0]
  }

  if (!nextFirstSelectedID) {
    nextFirstSelectedID = nextCommitID
  }

  nextSelectedIDs.add(nextCommitID)

  dispatch(
    setSelectedElements({
      scopeID: nextScopeID,
      firstSelectedID: nextFirstSelectedID,
      selectedIDs: nextSelectedIDs,
      lastSelectedID: nextCommitID,
    })
  )
}

const previousPartitionWithCommits = (review, partition) => {
  let partitionIndex = getPartitionIndex(review, partition)
  while (partitionIndex > 0) {
    --partitionIndex
    const partition = review.partitions.get(partitionIndex)
    if (partition.commits.size) return partition
  }
  return null
}

export const selectPreviousCommit = ({
  review,
  additive,
  selectionKey = null,
}) => (dispatch, getState) => {
  const state = getState()
  const {
    scopeID,
    firstSelectedID,
    lastSelectedID,
    selectedIDs,
    elementIDs,
  } = state.ui.selectionScope

  var currentCommitID = null
  var partition = null

  if (scopeID !== null) {
    var [key, partitionIndex] = scopeID.split(":")
    if (key === "commits") {
      partitionIndex = parseInt(partitionIndex, 10)
      partition = review.partitions.get(partitionIndex)
      currentCommitID = firstSelectedID
    }
  }

  var nextScopeID = scopeID
  var selector = null
  var nextCommitID = null
  var nextLastSelectedID = additive ? lastSelectedID : null
  var nextSelectedIDs = new Set(additive ? selectedIDs : [])

  if (currentCommitID !== null) {
    const currentCommitIndex = elementIDs.indexOf(currentCommitID)
    if (currentCommitIndex > 0) {
      nextCommitID = elementIDs[currentCommitIndex - 1]
    } else {
      if (additive) {
        return
      }
      nextScopeID = null
      if (selectionKey === null) {
        partition = previousPartitionWithCommits(review, partition)
        if (partition) {
          const partitionIndex = getPartitionIndex(review, partition)
          nextScopeID = `commits:${partitionIndex}`
          selector = `.partition${partitionIndex}`
          nextCommitID = partition.commits.last()
        }
      }
    }
  }

  if (nextScopeID === null) {
    if (selectionKey === null) {
      const partitionIndex = review.partitions.size - 1
      nextScopeID = `commits:${partitionIndex}`
      selector = `.partition${partitionIndex}`
      const partition = review.partitions.last()
      nextCommitID = partition.commits.last()
    } else {
      nextScopeID = "commits:0"
      selector = "." + selectionKey
      nextCommitID = null
    }
  }

  if (nextScopeID !== scopeID) {
    const elements = document.querySelectorAll(selector)
    dispatch(
      defineSelectionScope(nextScopeID, elements, (element) =>
        parseInt(element.dataset.commitId, 10)
      )
    )
    if (nextCommitID === null && elements.length) {
      nextCommitID = parseInt(
        elements[elements.length - 1].dataset.commitId,
        10
      )
    }
  } else if (nextCommitID === null) {
    nextCommitID = elementIDs[elementIDs.length - 1]
  }

  if (!nextLastSelectedID) {
    nextLastSelectedID = nextCommitID
  }

  nextSelectedIDs.add(nextCommitID)

  dispatch(
    setSelectedElements({
      scopeID: nextScopeID,
      firstSelectedID: nextCommitID,
      selectedIDs: nextSelectedIDs,
      lastSelectedID: nextLastSelectedID,
    })
  )
}
