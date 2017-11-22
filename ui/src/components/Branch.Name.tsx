import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import { useResource } from "../utils"

const useStyles = makeStyles((theme: Theme) => ({
  root: {
    ...theme.critic.monospaceFont,
    fontWeight: 500,
    background: theme.palette.secondary.light,
    borderColor: theme.palette.secondary.main,
    borderWidth: 1,
    borderStyle: "solid",
    borderRadius: 4,
    padding: "1px 6px",
  },
}))

type Props = {
  className?: string
  branchID: number
}

const BranchName: FunctionComponent<Props> = ({ className, branchID }) => {
  const classes = useStyles()
  const branches = useResource("branches")
  const branch = branches.byID.get(branchID)
  if (!branch) return null
  return <code className={clsx(className, classes.root)}>{branch.name}</code>
}

export default Registry.add("Branch.Name", BranchName)
