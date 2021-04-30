import React, { FunctionComponent } from "react"
import { useHistory } from "react-router"

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
  const history = useHistory()
  const review = useReview()
  if (!review) return null
  const callback = () =>
    dispatch(deleteReview(review.id)).then(() => history.replace("/"))
  return (
    <Confirm
      className={className}
      dialogID={kDialogID}
      title="Delete review?"
      accept={{
        label: "Delete review",
        callback,
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
