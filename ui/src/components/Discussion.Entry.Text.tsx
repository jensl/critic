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
import Paper from "@material-ui/core/Paper"

import Registry from "."
import MarkdownDocument from "./Markdown.Document"

const useStyles = makeStyles((theme) => ({
  discussionEntryText: {},
  markdown: { margin: theme.spacing(1, 2) },
}))

type Props = {
  className?: string
  text: string
}

const Text: React.FunctionComponent<Props> = ({ className, text }) => {
  const classes = useStyles()
  return (
    <Paper
      className={clsx(className, classes.discussionEntryText)}
      elevation={0}
    >
      <div className={classes.markdown}>
        {text.trim() ? (
          <MarkdownDocument>{text}</MarkdownDocument>
        ) : (
          <em>Empty comment</em>
        )}
      </div>
    </Paper>
  )
}

export default Registry.add("Discussion.Entry.Text", Text)
