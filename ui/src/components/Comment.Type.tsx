/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
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

import React, { FunctionComponent } from "react"

import Registry from "."
import Comment from "../resources/comment"

type OwnProps = {
  comment: Comment
}

const ChangesetCommentType: FunctionComponent<OwnProps> = ({ comment }) => {
  if (comment.type === "note") return <>Note by </>
  switch (comment.state) {
    case "open":
      return <>Open issue by </>
    case "addressed":
      return <>Addressed issue by </>
    case "resolved":
      return <>Resolved issue by </>
  }
}

export default Registry.add("Changeset.Comment.Type", ChangesetCommentType)
