import React from "react"

import PublishIcon from "@material-ui/icons/Publish"

import Registry from "."
import ReviewActionsButton from "./Review.Actions.Button"
import { kDialogID } from "./Dialog.Review.PublishChanges"
import { useDialog, useReview } from "../utils"
import { useUnpublished } from "../utils/Batch"

type Props = { className?: string }

const PublishChanges: React.FunctionComponent<Props> = ({ className }) => {
  const review = useReview()
  const unpublished = useUnpublished()
  const { openDialog } = useDialog(kDialogID)
  if (review.state !== "open" || !unpublished || unpublished.isEmpty)
    return null
  return (
    <ReviewActionsButton
      className={className}
      color="primary"
      onClick={() => openDialog()}
      label="Publish changes"
      icon={PublishIcon}
    />
  )
}

export default Registry.add("Review.Actions.PublishChanges", PublishChanges)
