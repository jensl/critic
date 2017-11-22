import React, { FunctionComponent } from "react"

import Typography from "@material-ui/core/Typography"

import Registry from "."
import Confirm from "./Dialog.Confirm"
import { dropReview } from "../actions/review"
import { useReview } from "../utils"
import { ReviewID } from "../resources/types"
import { useDispatch } from "../store"

export const kDialogID = "dropReview"

type Props = {
  className?: string
}

const DropReview: FunctionComponent<Props> = ({ className }) => {
  const dispatch = useDispatch()
  const review = useReview()
  if (!review) return null
  return (
    <Confirm
      className={className}
      dialogID={kDialogID}
      title="Drop review?"
      accept={{
        label: "Drop review",
        callback: () => dispatch(dropReview(review.id)),
      }}
    >
      <Typography variant="body1">
        Dropping a review makes it silently vanish from all involved users'
        dashboards. If it becomes relevant again, the review can be reopened and
        finished.
      </Typography>
    </Confirm>
  )
}

export default Registry.add("Dialog.Review.Drop", DropReview)
