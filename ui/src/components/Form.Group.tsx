import React from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."

const useStyles = makeStyles((theme) => ({
  formGroup: {
    border: "1px solid rgba(128, 128, 128, 0.5)",
    borderRadius: "4px",
    padding: theme.spacing(2, 3),
    position: "relative",
    margin: theme.spacing(1, 0, 2, 0),
  },
  label: {
    position: "absolute",
    top: "-10px",
    background: theme.palette.background.paper,
    padding: theme.spacing(0, 1),
    opacity: 0.9,
  },
}))

type Props = {
  className?: string
  label: string
}

const FormGroup: React.FunctionComponent<Props> = ({
  className,
  label,
  children,
}) => {
  const classes = useStyles()
  return (
    <fieldset className={clsx(className, classes.formGroup)}>
      <legend className={classes.label}>{label}</legend>
      {children}
    </fieldset>
  )
}

export default Registry.add("Form.Group", FormGroup)
