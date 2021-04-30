import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import CircularProgress from "@material-ui/core/CircularProgress"

import Registry from "."

const useStyles = makeStyles((theme) => ({
  loaderBlock: {
    width: "100%",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },

  small: {
    margin: theme.spacing(4, 0),
  },
  large: {
    height: "50vh",
  },

  progress: {},
}))

type OwnProps = {
  className?: string
  waitingFor?: string
  size?: "small" | "large"
}

const LoaderBlock: FunctionComponent<OwnProps> = ({
  className,
  waitingFor,
  size = "large",
}) => {
  const classes = useStyles()
  return (
    <div
      className={clsx(classes.loaderBlock, classes[size])}
      title={waitingFor}
    >
      <CircularProgress className={clsx(className, classes.progress)} />
    </div>
  )
}

export default Registry.add("Loader.Block", LoaderBlock)
