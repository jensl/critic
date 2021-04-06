import React, { useEffect } from "react"

import PublishIcon from "@material-ui/icons/Publish"

import Registry from "."
import { ReviewActionProps } from "./Review.Action"
import { kDialogID } from "./Dialog.Review.PublishChanges"
import { useUnpublished } from "../utils/Batch"

const PublishChanges: React.FunctionComponent<ReviewActionProps> = ({
  review,
  addPrimary,
}) => {
  const unpublished = useUnpublished()

  const label = "Publish changes"
  const icon = <PublishIcon />
  const effect = { dialogID: kDialogID }

  useEffect(() => {
    if (review.state === "open" && !unpublished?.isEmpty)
      return addPrimary({ label, icon, effect, color: "primary" })
  }, [review, unpublished])

  return null
}

export default Registry.add("Review.Actions.PublishChanges", PublishChanges)
