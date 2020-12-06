import React from "react"

import PublishIcon from "@material-ui/icons/Publish"

import Registry from "."
import ReviewActionsButton from "./Review.Actions.Button"
import { kDialogID } from "./Dialog.Review.PublishReview"
import { useHash, useReview, useSignedInUser, isReviewOwner } from "../utils"

type Props = { className?: string }

const PublishReview: React.FunctionComponent<Props> = ({ className }) => {
  const { updateHash } = useHash()
  const review = useReview()
  const signedInUser = useSignedInUser()
  if (
    !review ||
    review.state !== "draft" ||
    !isReviewOwner(review, signedInUser) ||
    review.branch === null
  )
    return null
  return (
    <ReviewActionsButton
      className={className}
      color="primary"
      onClick={() => updateHash({ dialog: kDialogID })}
      label="Publish review"
      icon={PublishIcon}
    />
  )
}

export default Registry.add("Review.Actions.PublishReview", PublishReview)
