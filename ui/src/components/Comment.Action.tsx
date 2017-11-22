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

import Button from "@material-ui/core/Button"

import Registry from "."
import Comment from "../resources/comment"

export type ActionProps = {
  className?: string
  comment: Comment
  size?: "small" | "medium" | "large"
}

type OwnProps = {
  onClick: () => void
}

const CommentAction: FunctionComponent<
  Omit<ActionProps, "comment"> & OwnProps
> = ({ className, size = "small", onClick, children }) => (
  <Button className={className} size={size} onClick={onClick}>
    {children}
  </Button>
)

export default Registry.add("Comment.Action", CommentAction)
