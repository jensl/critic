import React, { useEffect } from "react"

import DeleteForeverIcon from "@material-ui/icons/DeleteForever"

import Registry from "."
import { ReviewActionProps } from "./Review.Action"
import { kDialogID } from "./Dialog.Review.DiscardChanges"
import { useUnpublished } from "../utils/Batch"

const DiscardChanges: React.FunctionComponent<ReviewActionProps> = ({
  review,
  addSecondary,
}) => {
  const unpublished = useUnpublished()

  const label = "Discard changes"
  const icon = <DeleteForeverIcon />
  const effect = { dialogID: kDialogID }

  useEffect(() => {
    if (!unpublished?.isEmpty)
      return addSecondary({ label, icon, effect, color: "primary" })
  }, [review, unpublished])

  return null
}

export default Registry.add("Review.Actions.DiscardChanges", DiscardChanges)
