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

import Immutable from "immutable"

import { REVIEW_SUMMARIES_UPDATE } from "../actions/reviewSummary"

const Category = new Immutable.Record(
  {
    reviews: new Immutable.List(),
    hasMore: false,
  },
  "ReviewSummaries.Category"
)

const Categories = new Immutable.Record(
  {
    own: new Category(),
    other: new Category(),
    all: new Category(),
  },
  "ReviewSummaries.Category"
)

const reviewSummary = (state = new Categories(), action) => {
  switch (action.type) {
    case REVIEW_SUMMARIES_UPDATE:
      return state.set(action.category, new Category(action))

    default:
      return state
  }
}

export default reviewSummary
