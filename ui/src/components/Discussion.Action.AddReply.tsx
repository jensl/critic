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
import { createReply } from "../actions/reply"
import { useDispatch } from "../store"
import { useDiscussionContext } from "../utils/DiscussionContext"

const AddReply: React.FunctionComponent<ActionProps> = ({ ...props }) => {
  const dispatch = useDispatch()
  const { comment } = useDiscussionContext()
  if (
    comment === null ||
    comment.isDraft ||
    (comment.draftChanges && comment.draftChanges.reply)
  )
    return null
  const onClick = async () => {
    const reply = await dispatch(createReply(comment.id))
    console.log({ reply })
    if (reply) {
      dispatch({ type: "SET_FLAG", flag: `Discussion/editable:${comment.id}` })
      setTimeout(() => {
        const el = document.getElementById(
          `discussion_entry_edit_${comment.id}`
        )
        if (el) el.focus()
      }, 0)
    }
  }
  return (
    <Action onClick={onClick} {...props}>
      Add reply
    </Action>
  )
}

export default Registry.add("Discussion.Action.AddReply", AddReply)
