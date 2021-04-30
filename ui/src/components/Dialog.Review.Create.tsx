import React, { FunctionComponent } from "react"
import { useHistory } from "react-router"

import TextField from "@material-ui/core/TextField"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Confirm from "./Dialog.Confirm"
import { loadBranch, loadBranchCommits } from "../actions/branch"
import { createReview } from "../actions/review"
import { useResource, useResourceExtra, useSubscription } from "../utils"
import { useDispatch } from "../store"
import { BranchID } from "../resources/types"

export const getDialogID = (branchID: BranchID) =>
  `createReview,branch=${branchID}`

type Props = {
  className?: string
  branchID: BranchID
}

const CreateReview: FunctionComponent<Props> = ({ className, branchID }) => {
  const dispatch = useDispatch()
  const history = useHistory()
  const branch = useResource("branches", ({ byID }) => byID.get(branchID))
  const commitsByID = useResource("commits", ({ byID }) => byID)
  const commitIDs = useResourceExtra(
    "branchCommits",
    (byBranchID) => byBranchID.get(branchID)?.all,
  )
  useSubscription(loadBranch, [branchID])
  useSubscription(loadBranchCommits, [branchID])
  if (!branch || !commitIDs) return null
  const defaultSummary = () => {
    for (const commitID of commitIDs) {
      const summary = commitsByID.get(commitID)?.summary
      if (
        summary &&
        !summary.startsWith("fixup! ") &&
        !summary.startsWith("squash! ")
      )
        return summary
    }
    return ""
  }
  const callback = async () => {
    const summary = document.getElementById(
      "dialog-review-create-summary",
    ) as HTMLInputElement
    const review = await dispatch(
      createReview(branch.repository, commitIDs, summary.value),
    )
    history.push(`/review/${review.id}`)
  }
  return (
    <Confirm
      className={className}
      dialogID={getDialogID(branchID)}
      title="Create review?"
      accept={{
        label: "Create review",
        callback,
      }}
    >
      <Typography variant="body1" gutterBottom>
        Note: The review will be created as an unpublished draft. It can be
        deleted if you change your mind, and other users will not be notified
        until the review is published.
      </Typography>

      <TextField
        fullWidth
        id="dialog-review-create-summary"
        label="Review summary"
        defaultValue={defaultSummary()}
      />
    </Confirm>
  )
}

export default Registry.add("Dialog.Review.Create", CreateReview)
