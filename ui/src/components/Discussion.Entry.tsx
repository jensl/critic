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
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Edit from "./Discussion.Entry.Edit"
import Text from "./Discussion.Entry.Text"
import UserAvatar from "./User.Avatar"
import UserName from "./User.Name"
import { UserID } from "../resources/types"
import { useFlag } from "../utils/Flag"
import { useDiscussionContext } from "../utils/DiscussionContext"

const useStyles = makeStyles((theme) => ({
  discussionEntry: {
    display: "grid",
    gridTemplateColumns: `${theme.spacing(6)}px 1fr 1fr`,
    gridTemplateAreas: `
      "avatar header lines"
      "avatar text text"
    `,
  },
  avatar: {
    gridArea: "avatar",
    width: theme.spacing(5),
    height: theme.spacing(5),
  },
  header: {
    gridArea: "header",
    display: "flex",
    alignItems: "baseline",
  },
  authorName: {
    fontWeight: 500,
    marginLeft: theme.spacing(0.5),
  },
  text: {
    gridArea: "text",
    margin: theme.spacing(0.5, 0),
  },
  draft: {
    color: theme.palette.primary.main,
    fontWeight: "bold",
    textTransform: "uppercase",
    marginRight: theme.spacing(1),
  },
}))

type OwnProps = {
  className?: string
  entryType?: JSX.Element
  author: UserID
  timestamp: number
  isDraft: boolean
  text: string
}

type ConnectedProps = {}

const DiscussionEntry: FunctionComponent<OwnProps & ConnectedProps> = ({
  className,
  entryType,
  author,
  timestamp,
  text,
  isDraft,
}) => {
  const classes = useStyles()
  const { currentText, editable } = useDiscussionContext()
  const [showEdit] = useFlag(editable)
  return (
    <div className={clsx(className, classes.discussionEntry)}>
      <UserAvatar className={classes.avatar} userID={author} />
      <div className={classes.header}>
        {isDraft ? (
          <Typography variant="caption" className={classes.draft}>
            draft
          </Typography>
        ) : null}
        <Typography className={classes.header} variant="body2">
          {entryType}
          <UserName className={classes.authorName} userID={author} />
        </Typography>
      </div>
      {isDraft && showEdit && currentText !== null ? (
        <Edit className={classes.text} text={currentText} />
      ) : (
        <Text className={classes.text} text={text} />
      )}
    </div>
  )
}

export default Registry.add("Discussion.Entry", DiscussionEntry)
