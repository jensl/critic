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

import store from "../store"

const validBranchRegExp = new RegExp("^r/([-\\.\\w]+/)*[-\\.\\w]+$")

export const isValidBranchName = (name) => validBranchRegExp.test(name)

export const getDefaultBranchName = (review) => {
  const state = store.getState()
  if (review.branch !== null) {
    const branch = state.resource.branches.byID.get(review.branch)
    if (branch) return branch.name
  }
  var name = "r/"
  const { user } = state.ui.rest
  if (user) {
    name += user.name + "/"
  }
  if (review.summary) {
    name += review.summary
      .split(/[^.\w]+/g)
      .map((part) => part.toLowerCase())
      .join("-")
  }
  return name
}
