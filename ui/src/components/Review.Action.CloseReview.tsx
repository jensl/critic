import React, { useEffect } from "react"

import Registry from "."
import { kDialogID } from "./Dialog.Review.Close"
import { ReviewActionProps } from "./Review.Action"
import { isReviewOwner } from "../utils"

const CloseReview: React.FunctionComponent<ReviewActionProps> = ({
  review,
  signedInUser,
  addPrimary,
  addSecondary,
}) => {
  const label = "Close"
  const effect = { dialogID: kDialogID }

  useEffect(() => {
    if (review.canClose) {
      if (isReviewOwner(review, signedInUser))
        return addPrimary({ label, effect })
      else return addSecondary({ label, effect })
    }
  }, [review, signedInUser])

  return null
}

export default Registry.add("Review.Actions.CloseReview", CloseReview)
