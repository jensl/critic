import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import CircularProgress from "@material-ui/core/CircularProgress"

import Registry from "."

const useStyles = makeStyles({
  loaderBlock: {
    width: "100%",
    height: "50vh",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },

  progress: {},
})

type OwnProps = {
  className?: string
  waitingFor?: string
}

const LoaderBlock: FunctionComponent<OwnProps> = ({
  className,
  waitingFor,
}) => {
  const classes = useStyles()
  return (
    <div className={classes.loaderBlock} title={waitingFor}>
      <CircularProgress className={clsx(className, classes.progress)} />
    </div>
  )
}

export default Registry.add("Loader.Block", LoaderBlock)
