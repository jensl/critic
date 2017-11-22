import React from "react"

import Registry from "."
import ReviewActionsButton from "./Review.Actions.Button"
import { useHash, useReview } from "../utils"

type Props = {
  className?: string
}

const ReviewActionsIntegrate: React.FunctionComponent<Props> = ({
  className,
}) => {
  const { updateHash } = useHash()
  const review = useReview()
  if (!review || !review.isAccepted) return null
  return (
    <ReviewActionsButton
      className={className}
      onClick={() => updateHash({ dialog: "IntegrateReview" })}
      label="Integrate"
    />
  )
}

export default Registry.add("Review.Actions.Integrate", ReviewActionsIntegrate)
