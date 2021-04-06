import React, { useState } from "react"
import clsx from "clsx"

import Button from "@material-ui/core/Button"
import IconButton from "@material-ui/core/IconButton"
import ListItemIcon from "@material-ui/core/ListItemIcon"
import ListItemText from "@material-ui/core/ListItemText"
import MoreVertIcon from "@material-ui/icons/MoreVert"
import Menu from "@material-ui/core/Menu"
import MenuItem from "@material-ui/core/MenuItem"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import {
  ActionOnClick,
  ActionDialogID,
  PrimaryActionProps,
  SecondaryActionProps,
  ReviewActionProps,
} from "./Review.Action"
import Actions from "./Review.Actions"
import { useHash, useReview, useSignedInUser } from "../utils"

const useStyles = makeStyles((theme) => ({
  reviewActions: {
    margin: "1rem",
    display: "flex",
    flexDirection: "row",
    justifyContent: "flex-end",
    alignItems: "center",
  },
  moreButton: {},
  primaryAction: { marginRight: theme.spacing(1) },
}))

type ActionCommon = {
  key: string
}
type ActionPrimary = {
  primary: PrimaryActionProps
}
type ActionSecondary = {
  secondary: SecondaryActionProps
}
type Action = ActionCommon & (ActionPrimary | ActionSecondary)
type ActionByKey = { [key: string]: Action | null }

type Props = {
  className?: string
}

const ReviewDetailsActions: React.FunctionComponent<Props> = ({
  className,
}) => {
  const classes = useStyles()
  const review = useReview()
  const signedInUser = useSignedInUser()
  const { updateHash } = useHash()
  const [anchorEl, setAnchorEl] = useState<Element | null>(null)
  const [actions, setActions] = useState<ActionByKey>({})

  if (!review) return null

  const actionKeys = Object.keys(actions)

  const setAction = (action: Action) =>
    setActions((actions) => ({ ...actions, [action.key]: action }))

  const unsetAction = (key: string) => () =>
    setActions((actions) => ({ ...actions, [key]: null }))

  const getProps = (key: string): ReviewActionProps => ({
    review,
    signedInUser,
    addPrimary(props: PrimaryActionProps) {
      setAction({ key, primary: props })
      return unsetAction(key)
    },
    addSecondary(props: SecondaryActionProps) {
      setAction({ key, secondary: props })
      return unsetAction(key)
    },
  })

  const activateAction = (effect: ActionOnClick | ActionDialogID) => () => {
    if ("onClick" in effect) {
      effect.onClick()
    } else {
      updateHash({ dialog: effect.dialogID })
    }
    setAnchorEl(null)
  }

  const isPrimaryAction = (
    action: Action | null,
  ): action is ActionCommon & ActionPrimary => !!action && "primary" in action
  const isSecondaryAction = (
    action: Action | null,
  ): action is ActionCommon & ActionSecondary =>
    !!action && "secondary" in action

  const primaryActions = actionKeys
    .map((key) => actions[key])
    .filter(isPrimaryAction)
  const secondaryActions = actionKeys
    .map((key) => actions[key])
    .filter(isSecondaryAction)

  return (
    <div className={clsx(className, classes.reviewActions)}>
      <Actions getProps={getProps} />
      {primaryActions.map(({ key, primary }) => {
        const { label, icon, effect, ...buttonProps } = primary
        return (
          <Button
            key={key}
            className={classes.primaryAction}
            startIcon={icon}
            size="small"
            onClick={activateAction(effect)}
            {...buttonProps}
          >
            {label}
          </Button>
        )
      })}
      {secondaryActions.length !== 0 && (
        <>
          <IconButton
            className={classes.moreButton}
            onClick={(ev) => setAnchorEl(ev.target as Element)}
          >
            <MoreVertIcon />
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={anchorEl !== null}
            onClose={() => setAnchorEl(null)}
          >
            {secondaryActions.map(({ key, secondary }) => {
              const { label, icon, effect, ...menuItemProps } = secondary
              return (
                <MenuItem
                  key={key}
                  onClick={activateAction(effect)}
                  {...menuItemProps}
                >
                  {icon && <ListItemIcon>{icon}</ListItemIcon>}
                  <ListItemText primary={label} />
                </MenuItem>
              )
            })}
          </Menu>
        </>
      )}
    </div>
  )
}

export default Registry.add("Review.Details.Actions", ReviewDetailsActions)
