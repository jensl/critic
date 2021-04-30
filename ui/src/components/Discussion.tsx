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

import Registry from "."
import Entry from "./Discussion.Entry"
import Actions from "./Discussion.Actions"
import CommentType from "./Comment.Type"
import DeleteCommentDialog from "./Dialog.Comment.Delete"
import DeleteReplyDialog from "./Dialog.Reply.Delete"
import { Location } from "../actions/comment"
import Reply from "../resources/reply"
import { useResource, Value, Flag } from "../utils"
import { SetDiscussionContext } from "../utils/DiscussionContext"
import Comment from "../resources/comment"
import { useDispatch } from "../store"

const useStyles = makeStyles((theme) => ({
  discussion: {},
  entry: {
    margin: theme.spacing(1, 0),
  },
  reply: {
    marginLeft: theme.spacing(6),
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
    margin: theme.spacing(1, 0),
  },
}))

type OwnProps = {
  className?: string
  comment?: Comment
  location: Location | null
}

const Discussion: FunctionComponent<OwnProps> = ({
  className,
  comment = null,
  location = null,
}) => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const allReplies = useResource("replies")
  const entries = []
  if (comment === null && location === null) return null
  let replies: Reply[] | null = null
  let draftReply: Reply | null = null
  let currentText: Value<string> | null = null
  let editable: Flag | null = null
  let wasDeleted: () => any = () => null
  if (comment) {
    replies = []
    for (const replyID of comment.replies) {
      const reply = allReplies.get(replyID)
      if (!reply) return null
      replies.push(reply)
    }
    draftReply = allReplies.get(comment.draftChanges?.reply || -1) || null
    if (comment.isDraft || draftReply) {
      currentText = new Value<string>(
        `Discussion/currentText:${comment.id}`,
        draftReply ? draftReply.text : comment.text,
      )
      editable = new Flag(`Discussion/editable:${comment.id}`)
      wasDeleted = () => dispatch(currentText!.delete())
    }
    const commonProps = ({ author, timestamp, text }: Comment | Reply) => ({
      author,
      timestamp,
      text,
    })
    entries.push(
      <Entry
        key="main"
        className={classes.entry}
        entryType={<CommentType comment={comment} />}
        isDraft={comment.isDraft}
        {...commonProps(comment)}
      />,
      ...replies.map((reply) => (
        <Entry
          key={reply.id}
          className={clsx(classes.entry, classes.reply)}
          isDraft={reply.isDraft}
          {...commonProps(reply)}
        />
      )),
    )
  }
  return (
    <SetDiscussionContext
      comment={comment}
      replies={replies}
      draftReply={draftReply}
      currentText={currentText}
      editable={editable}
      location={location}
    >
      <div className={clsx(className, classes.discussion)}>
        {entries}
        <div className={classes.actions}>
          <Actions />
        </div>
      </div>
      {comment && comment.isDraft && (
        <DeleteCommentDialog comment={comment} callback={wasDeleted} />
      )}
      {draftReply && <DeleteReplyDialog reply={draftReply} />}
    </SetDiscussionContext>
  )
}

export default Registry.add("Discussion", Discussion)
