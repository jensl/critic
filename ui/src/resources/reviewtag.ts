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

import { combineReducers } from "redux"
import { immerable } from "immer"

import { primaryMap, lookupMap } from "../reducers/resource"

type ReviewTagData = {
  id: number
  name: string
  description: string
}

type ReviewTagProps = ReviewTagData

class ReviewTag {
  [immerable] = true

  constructor(
    readonly id: number,
    readonly name: string,
    readonly description: string,
  ) {}

  static new(props: ReviewTagProps) {
    return new ReviewTag(props.id, props.name, props.description)
  }

  static reducer = combineReducers({
    byID: primaryMap<ReviewTag, number>("reviewtags"),
    byName: lookupMap<ReviewTag, string, number>(
      "reviewtags",
      (tag) => tag.name,
    ),
  })

  get props(): ReviewTagProps {
    return this
  }
}

export default ReviewTag
