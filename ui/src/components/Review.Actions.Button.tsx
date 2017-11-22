import React from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Button from "@material-ui/core/Button"

import Registry from "."

const useStyles = makeStyles((theme) => ({
  reviewActionsButton: { marginRight: theme.spacing(1) },
  icon: { fontSize: 20 },
}))

type Props = {
  className?: string
  label: string
  variant?: "text" | "outlined" | "contained"
  color?: "inherit" | "primary" | "secondary"
  icon?: React.ElementType
  onClick: () => void
}

const ReviewActionsButton: React.FunctionComponent<Props> = ({
  className,
  label,
  icon,
  ...buttonProps
}) => {
  const classes = useStyles()
  let startIcon: JSX.Element | null = null
  if (icon) {
    const IconComponent = icon
    startIcon = <IconComponent className={classes.icon} />
  }
  return (
    <Button
      className={clsx(className, classes.reviewActionsButton)}
      startIcon={startIcon}
      size="small"
      {...buttonProps}
    >
      {label}
    </Button>
  )
}

export default Registry.add("Review.Actions.Button", ReviewActionsButton)
