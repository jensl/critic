import React, { FunctionComponent } from "react"

import Typography from "@material-ui/core/Typography"

import Registry from "."
import Confirm from "./Dialog.Confirm"
import { useDispatch } from "../store"
import { deleteComment } from "../actions/comment"
import Comment from "../resources/comment"

type Props = {
  comment: Comment
  callback: () => void
}

const DeleteComment: FunctionComponent<Props> = ({ comment, callback }) => {
  const dispatch = useDispatch()
  return (
    <Confirm
      dialogID={`deleteComment:${comment.id}`}
      title="Delete comment?"
      accept={{
        label: "Delete comment",
        callback: () => dispatch(deleteComment(comment.id)).then(callback),
      }}
    >
      <Typography variant="body1">
        Deleting an unpublished comment is immediate and irreversible. The text
        cannot be recovered later.
      </Typography>
    </Confirm>
  )
}

export default Registry.add("Dialog.Comment.Delete", DeleteComment)
