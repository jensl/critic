import React, { useEffect } from "react"

import Registry from "."
import { ReviewActionProps } from "./Review.Action"
import { isReviewOwner } from "../utils"

const Integrate: React.FunctionComponent<ReviewActionProps> = ({
  review,
  signedInUser,
  addPrimary,
  addSecondary,
}) => {
  const label = "Integrate"
  const effect = { dialogID: "integrate" }

  useEffect(() => {
    if (review.isAccepted && review.integration)
      if (isReviewOwner(review, signedInUser))
        return addPrimary({ label, effect })
      else return addSecondary({ label, effect })
  }, [review, signedInUser])

  return null
}

export default Registry.add("Review.Actions.Integrate", Integrate)
