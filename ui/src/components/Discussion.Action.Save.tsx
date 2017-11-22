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
import { setReplyText } from "../actions/reply"
import { setCommentText } from "../actions/comment"
import { useDispatch } from "../store"
import { useValueWithFallback } from "../utils/Value"
import { useDiscussionContext } from "../utils/DiscussionContext"
import { useFlag } from "../utils/Flag"

const Save: React.FunctionComponent<ActionProps> = ({ ...props }) => {
  const dispatch = useDispatch()
  const { comment, draftReply, currentText, editable } = useDiscussionContext()
  const currentTextValue = useValueWithFallback(currentText, "")
  const [showEdit, toggleShowEdit] = useFlag(editable)
  if (comment === null || currentText === null || !showEdit) return null
  const isModified = currentTextValue !== currentText.defaultValue
  const onClick = async () => {
    if (draftReply) {
      await dispatch(setReplyText(draftReply.id, currentTextValue))
    } else {
      await dispatch(setCommentText(comment.id, currentTextValue))
    }
    toggleShowEdit()
  }
  return (
    <Action
      onClick={onClick}
      disabled={!isModified}
      color="primary"
      variant="contained"
      {...props}
    >
      Save
    </Action>
  )
}

export default Registry.add("Discussion.Action.Save", Save)
