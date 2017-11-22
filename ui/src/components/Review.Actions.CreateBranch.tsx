import React from "react"

//import CreateBranchIcon from "@material-ui/icons/Publish"

import Registry from "."
import ReviewActionsButton from "./Review.Actions.Button"
import { kDialogID } from "./Dialog.Review.CreateBranch"
import { useHash, useReview, useSignedInUser, isReviewOwner } from "../utils"

type Props = {
  className?: string
}

const ReviewActionsCreateBranch: React.FunctionComponent<Props> = ({
  className,
}) => {
  const { updateHash } = useHash()
  const review = useReview()
  const signedInUser = useSignedInUser()
  if (!review || !isReviewOwner(review, signedInUser) || review.branch !== null)
    return null
  return (
    <ReviewActionsButton
      className={className}
      color="primary"
      onClick={() => updateHash({ dialog: kDialogID })}
      label="Create branch"
      //icon={CreateBranchIcon}
    />
  )
}

export default Registry.add(
  "Review.Actions.CreateBranch",
  ReviewActionsCreateBranch
)
