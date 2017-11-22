/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"
import Button from "@material-ui/core/Button"
import Dialog from "@material-ui/core/Dialog"
import DialogActions from "@material-ui/core/DialogActions"
import DialogContent from "@material-ui/core/DialogContent"
import DialogTitle from "@material-ui/core/DialogTitle"
import TextField from "@material-ui/core/TextField"

import Registry from "."
import WithProgress from "./Button.WithProgress"
import { useDialog, useResource } from "../utils"
import { login, FieldValues } from "../actions/session"
import { Field } from "../resources/session"
import { useDispatch, useSelector } from "../store"

export const kDialogID = "signIn"

const useStyles = makeStyles({
  wrapper: {
    position: "relative",
  },
  buttonProgress: {
    position: "absolute",
    top: "50%",
    left: "50%",
    marginTop: -12,
    marginLeft: -12,
  },
  form: {
    "& :first-child": {
      marginTop: 0,
    },
  },
})

const SignIn: FunctionComponent = () => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const { isOpen, closeDialog } = useDialog(kDialogID)
  const { signInPending, signInSuccessful, signInError } = useSelector(
    (state) => state.ui.session
  )
  const session = useResource("sessions").get("current")
  if (!session) return null
  const fieldID = (field: Field) => `signin_${field.identifier}`
  const doSignIn = async () => {
    const data: FieldValues = {}
    session.fields.forEach((field) => {
      data[field.identifier] = (document.getElementById(
        fieldID(field)
      ) as HTMLInputElement).value
    })
    if (await dispatch(login(data))) closeDialog()
  }
  const fields = session.fields.map((field) => {
    const hasError =
      !!signInError && signInError.code === `invalid:${field.identifier}`
    return (
      <TextField
        key={field.identifier}
        id={fieldID(field)}
        error={hasError}
        helperText={signInError && hasError ? signInError.message : null}
        label={field.label}
        type={field.hidden ? "password" : "text"}
        margin="normal"
        fullWidth
      />
    )
  })
  return (
    <Dialog
      open={isOpen}
      onClose={closeDialog}
      aria-labelledby="simple-dialog-title"
    >
      <DialogTitle id="simple-dialog-title">Sign in</DialogTitle>
      <DialogContent>
        <form className={classes.form}>{fields}</form>
      </DialogContent>
      <DialogActions>
        <WithProgress inProgress={signInPending} successful={signInSuccessful}>
          <Button
            color="primary"
            disabled={signInPending || signInSuccessful}
            onClick={doSignIn}
          >
            Sign in
          </Button>
        </WithProgress>
      </DialogActions>
    </Dialog>
  )
}

export default Registry.add("Dialog.SignIn", SignIn)
