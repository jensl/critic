import React from "react"
import clsx from "clsx"

import Button from "@material-ui/core/Button"
import MenuItem from "@material-ui/core/MenuItem"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."

const useStyles = makeStyles((theme) => ({
  reviewActionsButton: { marginRight: theme.spacing(1) },
  icon: { fontSize: 20 },
}))

export type ReviewActionProps = {
  className?: string
  primary?: boolean
}

type ButtonProps = {
  className?: string
  primary: boolean
  label: string
  variant?: "text" | "outlined" | "contained"
  color?: "inherit" | "primary" | "secondary"
  icon?: React.ElementType
  onClick: () => void
}

const ReviewActionsButton: React.FunctionComponent<ButtonProps> = ({
  className,
  primary,
  label,
  icon,
  onClick,
  ...buttonProps
}) => {
  const classes = useStyles()
  let startIcon: JSX.Element | null = null
  if (icon) {
    const IconComponent = icon
    startIcon = <IconComponent className={classes.icon} />
  }
  if (!primary) {
    return <MenuItem onClick={onClick}>{label}</MenuItem>
  }
  return (
    <Button
      className={clsx(className, classes.reviewActionsButton)}
      startIcon={startIcon}
      size="small"
      onClick={onClick}
      {...buttonProps}
    >
      {label}
    </Button>
  )
}

export default Registry.add("Review.Actions.Button", ReviewActionsButton)
