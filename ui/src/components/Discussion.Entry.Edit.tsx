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
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import TextareaAutosize from "@material-ui/core/TextareaAutosize"

import Registry from "."
import { Value, useValue } from "../utils"
import { useDiscussionContext } from "../utils/DiscussionContext"

const useStyles = makeStyles((theme) => ({
  discussionEntryEdit: {
    ...theme.typography.body1,
    padding: theme.spacing(1, 2),
    background: theme.palette.background.paper,
    color: theme.palette.text.primary,
  },
}))

type Props = {
  className?: string
  text: Value<string>
}

const Edit: React.FunctionComponent<Props> = ({ className, text }) => {
  const classes = useStyles()
  const [value, setValue] = useValue(text)
  const { comment } = useDiscussionContext()
  if (!comment) return null
  return (
    <TextareaAutosize
      className={clsx(className, classes.discussionEntryEdit)}
      id={`discussion_entry_edit_${comment.id}`}
      rows={3}
      defaultValue={value || ""}
      onChange={(ev) => setValue(ev.target.value)}
      autoFocus
    />
  )
}

export default Registry.add("Discussion.Entry.Edit", Edit)
