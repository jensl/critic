import React, { FunctionComponent, useEffect } from "react"

import DeleteIcon from "@material-ui/icons/Delete"

import Registry from "."
import { kDialogID } from "./Dialog.Review.Delete"
import { ReviewActionProps } from "./Review.Action"

const DeleteReview: FunctionComponent<ReviewActionProps> = ({
  review,
  addSecondary,
}) => {
  const label = "Delete"
  const icon = <DeleteIcon />
  const effect = { dialogID: kDialogID }

  useEffect(() => {
    if (review.state === "draft") return addSecondary({ label, icon, effect })
  }, [review])

  return null
}

export default Registry.add("Review.Actions.DeleteReview", DeleteReview)
