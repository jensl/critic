import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles, Theme } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."

const useStyles = makeStyles((theme: Theme) => ({
  root: {
    display: "flex",
    flexDirection: "row",
    alignItems: "center",
    minHeight: "2.5rem",

    [theme.breakpoints.down("sm")]: {
      flexDirection: "column",
      alignItems: "flex-start",
      paddingBottom: theme.spacing(1),
    },
  },
  heading: {
    [theme.breakpoints.up("md")]: {
      flexGrow: 0,
      textAlign: "right",
      marginRight: "1rem",
      flexBasis: "8em",
    },
  },
  value: {
    display: "flex",
    flexWrap: "wrap",
    flexGrow: 1,
    alignItems: "center",
  },
}))

type OwnProps = {
  className?: string
  heading: string
}

const DetailsRow: FunctionComponent<OwnProps> = ({
  className,
  heading,
  children,
}) => {
  const classes = useStyles()
  return (
    <div className={clsx(className, classes.root)}>
      <Typography className={classes.heading} variant="subtitle2">
        {heading}:
      </Typography>
      <div className={classes.value}>{children}</div>
    </div>
  )
}

export default Registry.add("Details.Row", DetailsRow)
