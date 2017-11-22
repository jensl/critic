import React, { FunctionComponent } from "react"

import Typography from "@material-ui/core/Typography"

import Registry from "."
import Confirm from "./Dialog.Confirm"
import { deleteReview } from "../actions/review"
import { useReview } from "../utils"
import { useDispatch } from "../store"

export const kDialogID = "deleteReview"

type Props = {
  className?: string
}

const DeleteReview: FunctionComponent<Props> = ({ className }) => {
  const dispatch = useDispatch()
  const review = useReview()
  if (!review) return null
  return (
    <Confirm
      className={className}
      dialogID={kDialogID}
      title="Delete review?"
      accept={{
        label: "Delete review",
        callback: () => dispatch(deleteReview(review.id)),
      }}
    >
      <Typography variant="body1">
        Deleting an unpublished review is immediate and irreversible; it removes
        all traces of the review from the system. Any branches (and commits)
        that existed before the review was created are left intact.
      </Typography>
    </Confirm>
  )
}

export default Registry.add("Dialog.Review.Delete", DeleteReview)
