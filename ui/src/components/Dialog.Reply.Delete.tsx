import React, { FunctionComponent } from "react"

import Typography from "@material-ui/core/Typography"

import Registry from "."
import Confirm from "./Dialog.Confirm"
import { useDispatch } from "../store"
import { deleteReply } from "../actions/reply"
import Reply from "../resources/reply"

type Props = {
  reply: Reply
}

const DeleteReply: FunctionComponent<Props> = ({ reply }) => {
  const dispatch = useDispatch()
  return (
    <Confirm
      dialogID={`deleteReply:${reply.id}`}
      title="Delete reply?"
      accept={{
        label: "Delete reply",
        callback: () => dispatch(deleteReply(reply.id)),
      }}
    >
      <Typography variant="body1">
        Deleting an unpublished reply is immediate and irreversible. The text
        cannot be recovered later.
      </Typography>
    </Confirm>
  )
}

export default Registry.add("Dialog.Reply.Delete", DeleteReply)
