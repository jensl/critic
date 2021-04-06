import React, { useEffect } from "react"

import Registry from "."
import { ReviewActionProps } from "./Review.Action"

const ReopenReview: React.FunctionComponent<ReviewActionProps> = ({
  review,
  addSecondary,
}) => {
  const label = "Reopen"
  const effect = { dialogID: "reopenReview" }

  useEffect(() => {
    if (review.canReopen) return addSecondary({ label, effect })
  }, [review])

  return null
}

export default Registry.add("Review.Actions.ReopenReview", ReopenReview)
