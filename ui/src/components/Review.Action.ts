import { ButtonProps } from "@material-ui/core/Button"
import { MenuItemProps } from "@material-ui/core/MenuItem"

import Review from "../resources/review"
import User from "../resources/user"

type ActionLabel = {
  label: string
  icon?: JSX.Element
}

export type ActionOnClick = {
  onClick: () => void
}

export type ActionDialogID = {
  dialogID: string
}

type ActionEffect = { effect: ActionOnClick | ActionDialogID }
type ActionProps = ActionLabel & ActionEffect

export type PrimaryActionProps = ActionProps & Partial<ButtonProps>
export type SecondaryActionProps = ActionProps &
  Partial<Omit<MenuItemProps, "button">>

type RemoveActionCallback = () => void

type AddPrimary = (props: PrimaryActionProps) => RemoveActionCallback
type AddSecondary = (props: SecondaryActionProps) => RemoveActionCallback

export type ReviewActionProps = {
  review: Review
  signedInUser: User | null

  addPrimary: AddPrimary
  addSecondary: AddSecondary
}
