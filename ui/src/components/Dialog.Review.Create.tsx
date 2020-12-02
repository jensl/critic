import React, { FunctionComponent } from "react"

import Typography from "@material-ui/core/Typography"

import Registry from "."
import Confirm from "./Dialog.Confirm"
import { loadBranch, loadBranchCommits } from "../actions/branch"
import { createReview } from "../actions/review"
import {
  useResource,
  useResourceExtra,
  useReview,
  useSubscription,
  useSubscriptionIf,
} from "../utils"
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
  const branch = useResource("branches", ({ byID }) => byID.get(branchID))
  const commitIDs = useResourceExtra(
    "branchCommits",
    (byBranchID) => byBranchID.get(branchID)?.all,
  )
  useSubscription(loadBranch, { branchID })
  useSubscription(loadBranchCommits, branchID)
  if (!branch || !commitIDs) return null
  return (
    <Confirm
      className={className}
      dialogID={getDialogID(branchID)}
      title="Create review?"
      accept={{
        label: "Create review",
        callback: () => dispatch(createReview(branch.repository, commitIDs)),
      }}
    >
      <Typography variant="body1">
        Note: The review will be created as an unpublished draft. It can be
        deleted if you change your mind, and other users will not be notified
        until the review is published.
      </Typography>
    </Confirm>
  )
}

export default Registry.add("Dialog.Review.Create", CreateReview)
