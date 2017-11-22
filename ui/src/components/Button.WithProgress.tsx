import React from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import CircularProgress from "@material-ui/core/CircularProgress"

import Registry from "."

const useStyles = makeStyles((theme) => ({
  WithProgress: { position: "relative" },
  overlay: {
    position: "absolute",
    top: "50%",
    left: "50%",
    marginTop: -12,
    marginLeft: -12,
  },
}))

type Props = {
  className?: string
  inProgress?: boolean
  successful?: boolean
}

const ButtonWithProgress: React.FunctionComponent<Props> = ({
  className,
  inProgress = false,
  successful = false,
  children,
}) => {
  const classes = useStyles()
  return (
    <div className={clsx(className, classes.WithProgress)}>
      {children}
      {inProgress && <CircularProgress size={24} className={classes.overlay} />}
    </div>
  )
}

export default Registry.add("Button.WithProgress", ButtonWithProgress)
