import React from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."

const useStyles = makeStyles((theme) => ({
  formGroup: {
    border: "1px solid rgba(128, 128, 128, 0.5)",
    borderRadius: "4px",
    padding: theme.spacing(1, 3, 2, 3),
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
  error: {
    color: theme.palette.error.main,
    borderColor: theme.palette.error.main,
  },
}))

type Props = {
  className?: string
  label: string
  error?: boolean
}

const FormGroup: React.FunctionComponent<Props> = ({
  className,
  label,
  error = false,
  children,
}) => {
  const classes = useStyles()
  return (
    <fieldset
      className={clsx(className, classes.formGroup, error && classes.error)}
    >
      <legend className={clsx(classes.label, error && classes.error)}>
        {label}
      </legend>
      {children}
    </fieldset>
  )
}

export default Registry.add("Form.Group", FormGroup)
