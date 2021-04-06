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
import { resolveIssue } from "../actions/comment"
import { useDispatch } from "../store"
import { useDiscussionContext } from "../utils/DiscussionContext"

const ResolveIssue: React.FunctionComponent<ActionProps> = ({ ...props }) => {
  const dispatch = useDispatch()
  const { comment } = useDiscussionContext()
  if (
    !comment ||
    comment.isDraft ||
    comment.effectiveType !== "issue" ||
    comment.effectiveState !== "open"
  )
    return null
  const onClick = async () => {
    await dispatch(resolveIssue(comment.id))
  }
  return (
    <Action onClick={onClick} {...props}>
      Resolve issue
    </Action>
  )
}

export default Registry.add("Discussion.Action.ResolveIssue", ResolveIssue)
