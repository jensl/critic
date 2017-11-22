import React from "react"

import Registry from "."
import ReviewActionsButton from "./Review.Actions.Button"
import { useHash, useReview, useSignedInUser, isReviewOwner } from "../utils"

type Props = {
  className?: string
}
const ReviewActionsReopen: React.FunctionComponent<Props> = ({ className }) => {
  const { updateHash } = useHash()
  const review = useReview()
  const signedInUser = useSignedInUser()
  if (
    !review ||
    (review.state !== "dropped" && review.state !== "closed") ||
    review.isAccepted ||
    !isReviewOwner(review, signedInUser)
  )
    return null
  return (
    <ReviewActionsButton
      className={className}
      onClick={() => updateHash({ dialog: "dropReview" })}
      label="Reopen"
    />
  )
}

export default Registry.add("Review.Actions.Reopen", ReviewActionsReopen)
