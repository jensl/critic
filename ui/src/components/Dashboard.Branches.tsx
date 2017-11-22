import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."

const useStyles = makeStyles({
  dashboardBranches: {},
})

type OwnProps = {
  className?: string
}

const DashboardBranches: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  return <div className={clsx(className, classes.dashboardBranches)} />
}

export default Registry.add("Dashboard.Branches", DashboardBranches)
