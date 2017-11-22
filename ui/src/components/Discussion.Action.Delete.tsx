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

import React from "react"

import Registry from "."
import Action, { ActionProps } from "./Discussion.Action"
import { useDiscussionContext } from "../utils/DiscussionContext"
import { useFlag, useHash } from "../utils"
import { deleteComment } from "../actions/comment"
import { deleteReply } from "../actions/reply"
import { useDispatch } from "../store"

const Delete: React.FunctionComponent<ActionProps> = ({ ...props }) => {
  const dispatch = useDispatch()
  const { updateHash } = useHash()
  const { comment, draftReply, editable } = useDiscussionContext()
  const [showEdit] = useFlag(editable)
  if (comment === null || !(comment.isDraft || draftReply) || showEdit)
    return null
  const onClick = draftReply
    ? () => {
        if (draftReply.text.trim())
          updateHash({ dialog: `deleteReply:${draftReply.id}` })
        else dispatch(deleteReply(draftReply.id))
      }
    : () => {
        if (comment.text.trim())
          updateHash({ dialog: `deleteComment:${comment.id}` })
        else dispatch(deleteComment(comment.id))
      }
  return (
    <Action onClick={onClick} {...props}>
      Delete
    </Action>
  )
}

export default Registry.add("Discussion.Action.Delete", Delete)
