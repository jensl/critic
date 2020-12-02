import React from "react"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."

const useStyles = makeStyles((theme) => ({
  buttons: {
    display: "flex",
    justifyContent: "flex-end",
    marginTop: theme.spacing(2),

    "& > *": {
      marginLeft: theme.spacing(1),
    },
  },
}))

const Buttons: React.FunctionComponent<{}> = ({ children }) => {
  const classes = useStyles()
  return <div className={classes.buttons}>{children}</div>
}

export default Registry.add("Settings.Buttons", Buttons)
