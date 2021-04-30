import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."

import { useBranch } from "../utils"

const useStyles = makeStyles({
  branchTitle: {},
})

type OwnProps = {
  className?: string
}

const Title: FunctionComponent<OwnProps> = () => {
  const classes = useStyles()
  const branch = useBranch()
  return (
    <Typography className={classes.branchTitle} variant="h4" gutterBottom>
      {branch.name}
    </Typography>
  )
}

export default Registry.add("Branch.Title", Title)
