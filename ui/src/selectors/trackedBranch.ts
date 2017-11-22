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

import { castImmutable } from "immer"
import { createSelector } from "reselect"

import { getRepository } from "./repository"
import { State } from "../state"
import { RepositoryID } from "../resources/types"
import TrackedBranch from "../resources/trackedbranch"

const getTrackedBranches = (state: State) => state.resource.trackedbranches.byID

export const getTrackedBranchesPerRepository = createSelector(
  getTrackedBranches,
  (trackedBranches) => {
    const result = new Map<RepositoryID, Set<TrackedBranch>>()
    for (const trackedBranch of trackedBranches.values()) {
      const repositoryID = trackedBranch.repository
      let perRepository = result.get(repositoryID)
      if (!perRepository) {
        perRepository = new Set()
        result.set(repositoryID, perRepository)
      }
      perRepository.add(trackedBranch)
    }
    return castImmutable(result)
  }
)

export const getTrackedBranchesForRepository = createSelector(
  getTrackedBranchesPerRepository,
  getRepository,
  (trackedBranchesPerRepository, repository) => {
    if (!repository) return null
    return trackedBranchesPerRepository.get(repository.id) || null
  }
)
