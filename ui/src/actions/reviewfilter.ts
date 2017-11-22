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

import { createResources } from "../resources"
import { ReviewID, UserID } from "../resources/types"
import ReviewFilter from "../resources/reviewfilter"
import { AsyncThunk } from "../state"

interface ReviewFilterInput {
  subject?: UserID | string
  type: "reviewer" | "watcher" | "ignored"
  path: string
  review?: ReviewID
  default_scope?: boolean
  scopes?: (number | string)[]
}

export const createReviewFilters = (
  reviewFilters: ReviewFilterInput[]
): AsyncThunk<ReviewFilter[]> =>
  createResources("reviewfilters", reviewFilters, {
    include: ["reviews", "changesets", "reviewablefilechanges"],
  })
