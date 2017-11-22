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

import { primaryMap } from "../reducers/resource"
import { ReplyID, CommentID, UserID } from "./types"

type ReplyData = {
  id: ReplyID
  is_draft: boolean
  comment: CommentID
  author: UserID
  timestamp: number
  text: string
}

type ReplyProps = ReplyData

class Reply {
  constructor(
    readonly id: ReplyID,
    readonly isDraft: boolean,
    readonly comment: CommentID,
    readonly author: UserID,
    readonly timestamp: number,
    readonly text: string
  ) {}

  static new(props: ReplyProps) {
    return new Reply(
      props.id,
      props.is_draft,
      props.comment,
      props.author,
      props.timestamp,
      props.text
    )
  }

  static reducer = primaryMap<Reply, ReplyID>("replies")

  get props(): ReplyProps {
    return { ...this, is_draft: this.isDraft }
  }
}

export default Reply

export type Replies = ReturnType<typeof Reply.reducer>
