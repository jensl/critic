import React, { useEffect } from "react"

import PublishIcon from "@material-ui/icons/Publish"

import Registry from "."
import { ReviewActionProps } from "./Review.Action"
import { kDialogID } from "./Dialog.Review.PublishReview"
import { useHash, useReview, useSignedInUser, isReviewOwner } from "../utils"

const PublishReview: React.FunctionComponent<ReviewActionProps> = ({
  review,
  addPrimary,
}) => {
  const label = "Publish review"
  const icon = <PublishIcon />
  const effect = { dialogID: kDialogID }

  useEffect(() => {
    if (review.canPublish)
      return addPrimary({ label, icon, effect, color: "primary" })
  }, [review])

  return null
}

export default Registry.add("Review.Actions.PublishReview", PublishReview)
