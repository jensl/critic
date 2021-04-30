import React, { FunctionComponent } from "react"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Title from "./Branch.ListItem.Title"
import Metadata from "./Branch.ListItem.Metadata"
import { BranchID } from "../resources/types"
import { usePrefix, useResource } from "../utils"

const useStyles = makeStyles((theme) => ({
  branchListItem: {
    display: "flex",
    paddingTop: theme.spacing(1),
    paddingBottom: theme.spacing(1),
    textDecoration: "none",
    color: "inherit",

    "&:hover": {
      background: theme.palette.secondary.light,
      cursor: "pointer",
      borderRadius: 4,
    },
  },

  title: {
    ...theme.critic.monospaceFont,
    flexGrow: 1,
    paddingLeft: theme.spacing(2),
  },
  metadata: {
    ...theme.critic.monospaceFont,
    flexGrow: 0,
    paddingRight: theme.spacing(2),
  },
}))

type OwnProps = {
  className?: string
  branchID: BranchID
}

const BranchListItem: FunctionComponent<OwnProps> = ({
  className,
  branchID,
}) => {
  const classes = useStyles()
  const prefix = usePrefix()
  const branch = useResource("branches", ({ byID }) => byID.get(branchID))
  if (!branch) return null
  return (
    <Link
      to={`${prefix}/branch/${branch.name}`}
      className={clsx(className, classes.branchListItem)}
    >
      <Title className={classes.title} branch={branch} />
      <Metadata className={classes.metadata} branch={branch} />
    </Link>
  )
}

export default Registry.add("Branch.ListItem", BranchListItem)
