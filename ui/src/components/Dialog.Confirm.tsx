import React, { FunctionComponent } from "react"

import Button from "@material-ui/core/Button"
import Dialog from "@material-ui/core/Dialog"
import DialogActions from "@material-ui/core/DialogActions"
import DialogContent from "@material-ui/core/DialogContent"
import DialogTitle from "@material-ui/core/DialogTitle"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import { useDialog } from "../utils"
import { assertNotNull } from "../debug"

type Accept = {
  label: string
  callback: () => Promise<any>
}
type Deny = {
  label: string
  callback: () => any
}

type OwnProps = {
  className?: string
  dialogID?: string
  open?: boolean
  onClose?: () => void
  title: string
  text?: string
  accept: Accept
  deny?: Deny
}

const Confirm: FunctionComponent<OwnProps> = ({
  className,
  dialogID,
  open,
  onClose,
  title,
  text = null,
  children,
  accept,
  deny = null,
}) => {
  const { isOpen, closeDialog } = useDialog(dialogID || "notused")
  if (dialogID) {
    open = isOpen
    onClose = closeDialog
  } else {
    assertNotNull(onClose)
    assertNotNull(open)
  }
  if (!deny) deny = { label: "Do nothing", callback: onClose }
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        {text && <Typography variant="body1">{text}</Typography>}
        {children}
      </DialogContent>
      <DialogActions>
        <Button onClick={deny.callback}>{deny.label}</Button>
        <Button
          onClick={() => accept.callback().then(onClose)}
          color="primary"
          variant="contained"
        >
          {accept.label}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default Registry.add("Dialog.Confirm", Confirm)
