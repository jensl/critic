import React, { useEffect } from "react"

import Registry from "."
import { kDialogID } from "./Dialog.Review.Drop"
import { ReviewActionProps } from "./Review.Action"
import { isReviewOwner } from "../utils"

const DropReview: React.FunctionComponent<ReviewActionProps> = ({
  review,
  signedInUser,
  addSecondary,
}) => {
  const label = "Drop review"
  const effect = { dialogID: kDialogID }

  useEffect(() => {
    if (review.canDrop) return addSecondary({ label, effect })
  }, [review, signedInUser])

  return null
}

export default Registry.add("Review.Actions.DropReview", DropReview)
