import React, { useState } from "react"

import Button from "@material-ui/core/Button"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { ActionProps } from "./Changeset.Action"
import {
  all,
  any,
  count,
  sum,
  useChangeset,
  useReview,
  useSignedInUser,
} from "../utils"
import { useDispatch, useSelector } from "../store"
import { markAllAsReviewed } from "../actions/reviewableFilechange"
import { useRequireSession } from "./Dialog.SignIn"
import { getReviewableFileChangesForChangeset } from "../selectors/reviewableFileChange"
import AssignChanges, {
  AssignChangesReason,
} from "./Dialog.Review.AssignChanges"

const useStyles = makeStyles({
  markAllAsReviewed: {
    marginLeft: "auto",
  },
})

const MarkAllAsReviewed: React.FunctionComponent<ActionProps> = () => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const signedInUser = useSignedInUser()
  const review = useReview()
  const { changeset } = useChangeset()
  const rfcsByFile = useSelector((state) =>
    getReviewableFileChangesForChangeset(state, { review, changeset }),
  )
  const [requireSession, signInDialog] = useRequireSession(
    "You need to sign in before you can mark changes as reviewed.",
  )
  const [
    assignChangesReason,
    setAssignChangesReason,
  ] = useState<AssignChangesReason | null>(null)

  if (!review) return null

  const countTotal = rfcsByFile
    ? sum(rfcsByFile.values(), (rfcs) => rfcs.size)
    : 0
  const countAssigned =
    signedInUser && rfcsByFile
      ? sum(rfcsByFile.values(), (rfcs) =>
          count(rfcs, (rfc) => rfc.assignedReviewers.has(signedInUser.id)),
        )
      : 0
  const countReviewed =
    signedInUser && rfcsByFile && countAssigned !== 0
      ? sum(rfcsByFile.values(), (rfcs) =>
          count(rfcs, (rfc) => rfc.isReviewedBy(signedInUser.id)),
        )
      : 0

  console.log({ countTotal, countAssigned, countReviewed })

  const onClick = async () => {
    if (await requireSession()) {
      await dispatch(markAllAsReviewed(review, changeset))
      if (countAssigned === 0) setAssignChangesReason("nothing-assigned")
      else if (countAssigned < countTotal)
        setAssignChangesReason("something-unassigned")
    }
  }

  return (
    <>
      <Button
        className={classes.markAllAsReviewed}
        disabled={countReviewed === countTotal}
        onClick={onClick}
      >
        Mark all as reviewed
      </Button>
      {signInDialog}
      {assignChangesReason && (
        <AssignChanges
          open
          onClose={() => setAssignChangesReason(null)}
          reason={assignChangesReason}
        />
      )}
    </>
  )
}

export default Registry.add(
  "Changeset.Action.MarkAllAsReviewed",
  MarkAllAsReviewed,
)
