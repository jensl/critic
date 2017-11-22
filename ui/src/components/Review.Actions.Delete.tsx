import React, { FunctionComponent } from "react"

import DeleteIcon from "@material-ui/icons/Delete"

import Registry from "."
import Delete from "./Review.Actions.Button"
import { useHash, useReview, useSignedInUser, isReviewOwner } from "../utils"

type Props = {
  className?: string
}

const ReviewActionsDelete: FunctionComponent<Props> = ({ className }) => {
  const { updateHash } = useHash()
  const review = useReview()
  const signedInUser = useSignedInUser()
  if (
    !review ||
    review.state !== "draft" ||
    !isReviewOwner(review, signedInUser)
  )
    return null
  return (
    <Delete
      className={className}
      onClick={() => updateHash({ dialog: "deleteReview" })}
      label="Delete"
      icon={DeleteIcon}
    />
  )
}

export default Registry.add("Review.Actions.Delete", ReviewActionsDelete)
