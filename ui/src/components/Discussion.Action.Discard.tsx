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
import { useFlag } from "../utils/Flag"
import { useDispatch } from "../store"
import { deleteComment } from "../actions/comment"
import { deleteReply } from "../actions/reply"

const Discard: React.FunctionComponent<ActionProps> = ({ ...props }) => {
  const dispatch = useDispatch()
  const { comment, draftReply, currentText, editable } = useDiscussionContext()
  const [showEdit, toggleShowEdit] = useFlag(editable)
  if (comment === null || currentText === null || !showEdit) return null
  const onClick = () => {
    if (draftReply) {
      if (!draftReply.text) dispatch(deleteReply(draftReply.id))
    } else {
      if (!comment.text) dispatch(deleteComment(comment.id))
    }
    toggleShowEdit()
  }
  return (
    <Action onClick={onClick} {...props}>
      Discard
    </Action>
  )
}

export default Registry.add("Discussion.Action.Discard", Discard)
