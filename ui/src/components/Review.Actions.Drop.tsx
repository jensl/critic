import React from "react"

import Registry from "."
import ReviewActionsButton from "./Review.Actions.Button"
import { useHash, useReview, useSignedInUser, isReviewOwner } from "../utils"

type Props = {
  className?: string
}

const ReviewActionsDrop: React.FunctionComponent<Props> = ({ className }) => {
  const { updateHash } = useHash()
  const review = useReview()
  const signedInUser = useSignedInUser()
  if (
    !review ||
    review.state !== "open" ||
    review.isAccepted ||
    !isReviewOwner(review, signedInUser)
  )
    return null
  return (
    <ReviewActionsButton
      className={className}
      onClick={() => updateHash({ dialog: "dropReview" })}
      label="Drop"
    />
  )
}

export default Registry.add("Review.Actions.Drop", ReviewActionsDrop)
