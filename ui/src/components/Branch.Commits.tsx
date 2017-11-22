import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Container from "@material-ui/core/Container"
import Paper from "@material-ui/core/Paper"

import Registry from "."
import CommitList from "./Commit.List"
import { loadBranchCommits } from "../actions/branch"
import { useSubscription, useResourceExtra } from "../utils"
import Branch from "../resources/branch"

const useStyles = makeStyles((theme) => ({
  branchCommits: {
    padding: `${theme.spacing(1)}px ${theme.spacing(3)}px`,
  },
}))

type Props = {
  className?: string
  pathPrefix?: string
  branch: Branch
  offset?: number
  count?: number
}

const BranchCommits: FunctionComponent<Props> = ({
  className,
  pathPrefix = "",
  branch,
  offset = 0,
  count = 25,
}) => {
  const classes = useStyles()
  const branchCommits = useResourceExtra("branchCommits")
  useSubscription(loadBranchCommits, branch.id, { offset, count })
  const { all: commitIDs = null } = branchCommits.get(branch.id) || {}
  if (!commitIDs) return null
  pathPrefix += `/branch/${branch.name}`
  return (
    <Container maxWidth="lg">
      <Paper className={clsx(className, classes.branchCommits)}>
        <CommitList
          pathPrefix={pathPrefix}
          scopeID={`branch_${branch.id}`}
          commitIDs={commitIDs}
        />
      </Paper>
    </Container>
  )
}

export default Registry.add("Branch.Commits", BranchCommits)
