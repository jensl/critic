import React, { useEffect } from "react"

//import CreateBranchIcon from "@material-ui/icons/Publish"

import Registry from "."
import { ReviewActionProps } from "./Review.Action"
import { kDialogID } from "./Dialog.Review.CreateBranch"

const CreateBranch: React.FunctionComponent<ReviewActionProps> = ({
  review,
  addPrimary,
}) => {
  const label = "Create branch"
  const effect = { dialogID: kDialogID }

  useEffect(() => {
    if (review.branch === null)
      return addPrimary({ label, effect, color: "primary" })
  }, [review])

  return null
}

export default Registry.add("Review.Actions.CreateBranch", CreateBranch)
