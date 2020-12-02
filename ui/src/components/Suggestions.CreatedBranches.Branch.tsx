import React from "react"

import Button from "@material-ui/core/Button"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import BranchName from "./Branch.Name"
import RepositoryPath from "./Repository.Path"
import CreateReview, { getDialogID } from "./Dialog.Review.Create"
import { useDialog, useResource } from "../utils"
import { BranchID } from "../resources/types"

const useStyles = makeStyles((theme) => ({
  branch: {
    flexGrow: 1,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  details: {},
  actions: {},
  createReview: {},
}))

type Props = {
  className?: string
  branchID: BranchID
}

const Branch: React.FunctionComponent<Props> = ({ className, branchID }) => {
  const classes = useStyles()
  const branch = useResource("branches", ({ byID }) => byID.get(branchID))
  const { openDialog } = useDialog(getDialogID(branchID))
  if (!branch) return null
  return (
    <div className={classes.branch}>
      <div className={classes.details}>
        <BranchName branchID={branchID} link />
        {` containing ${branch.size || "no"} commits`}
        {branch.baseBranch !== null && (
          <>
            {" based on "}
            <BranchName branchID={branch.baseBranch} link />
          </>
        )}
        {" in "}
        <RepositoryPath repositoryID={branch.repository} link />
      </div>
      <div className={classes.actions}>
        {branch.size !== 0 && (
          <>
            <Button
              className={classes.createReview}
              size="small"
              onClick={() => openDialog()}
            >
              Create review
            </Button>
            <CreateReview branchID={branchID} />
          </>
        )}
      </div>
    </div>
  )
}

export default Registry.add("Suggestions.CreatedBranches.Branch", Branch)
