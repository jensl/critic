/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the
); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an
 BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import { immerable } from "immer"

import { primaryMap } from "../reducers/resource"

type ReviewFilterProps = {
  id: number
  subject: number
  review: number
  type: "reviewer" | "watcher" | "ignored"
  path: string
  creator: number
}

class ReviewFilter {
  [immerable] = true

  constructor(
    readonly id: number,
    readonly subject: number,
    readonly review: number,
    readonly type: "reviewer" | "watcher" | "ignored",
    readonly path: string,
    readonly creator: number,
  ) {}

  static new(props: ReviewFilterProps) {
    return new ReviewFilter(
      props.id,
      props.subject,
      props.review,
      props.type,
      props.path,
      props.creator,
    )
  }

  static reducer = primaryMap<ReviewFilter, number>("reviewfilters")

  get props(): ReviewFilterProps {
    return this
  }
}

export default ReviewFilter
