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

import React, { FunctionComponent, useState } from "react"

import { makeStyles } from "@material-ui/core/styles"
import Button from "@material-ui/core/Button"
import Dialog from "@material-ui/core/Dialog"
import DialogActions from "@material-ui/core/DialogActions"
import DialogContent from "@material-ui/core/DialogContent"
import DialogTitle from "@material-ui/core/DialogTitle"
import TextField from "@material-ui/core/TextField"
import Alert from "@material-ui/lab/Alert"

import Registry from "."
import WithProgress from "./Button.WithProgress"
import { useDialog, useResource, useSignedInUser } from "../utils"
import { login, FieldValues } from "../actions/session"
import { Field } from "../resources/session"
import { useDispatch, useSelector } from "../store"
import User from "../resources/user"

export const kDialogID = "signIn"

const useStyles = makeStyles((theme) => ({
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
  alert: {
    marginBottom: theme.spacing(1),
  },
}))

type Props = {
  global?: boolean
  callback?: ((user: User | null) => void) | null
  reason?: string
}

const SignIn: FunctionComponent<Props> = ({
  global = false,
  callback,
  reason,
}) => {
  const classes = useStyles()
  const dispatch = useDispatch()
  const { isOpen, closeDialog } = useDialog(kDialogID)
  const { signInPending, signInSuccessful, signInError } = useSelector(
    (state) => state.ui.session,
  )
  const session = useResource("sessions").get("current")
  if (!session) return null
  const fieldID = (field: Field) => `signin_${field.identifier}`
  const doSignIn = async () => {
    const data: FieldValues = {}
    session.fields.forEach((field) => {
      data[field.identifier] = (document.getElementById(
        fieldID(field),
      ) as HTMLInputElement).value
    })
    const user = await dispatch(login(data))
    if (user) {
      if (callback) callback(user)
      else closeDialog()
    }
  }
  const fields = session.fields.map((field, index) => {
    const hasError = signInError?.code === `invalid:${field.identifier}`
    return (
      <TextField
        key={field.identifier}
        id={fieldID(field)}
        error={hasError}
        helperText={hasError ? signInError?.message : undefined}
        label={field.label}
        type={field.hidden ? "password" : "text"}
        margin="normal"
        fullWidth
        autoFocus={index === 0}
      />
    )
  })

  const onClose = () => {
    if (global) closeDialog()
    else if (callback) callback(null)
  }

  return (
    <Dialog
      open={global ? isOpen : !!callback}
      onClose={onClose}
      aria-labelledby="simple-dialog-title"
    >
      <form
        className={classes.form}
        onSubmit={(ev) => {
          doSignIn()
          ev.preventDefault()
        }}
      >
        <DialogTitle id="simple-dialog-title">Sign in</DialogTitle>
        <DialogContent>
          {reason && (
            <Alert className={classes.alert} severity="info">
              {reason}
            </Alert>
          )}
          {fields}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <WithProgress
            inProgress={signInPending}
            successful={signInSuccessful}
          >
            <Button
              color="primary"
              variant="contained"
              disabled={signInPending || signInSuccessful}
              type="submit"
            >
              Sign in
            </Button>
          </WithProgress>
        </DialogActions>
      </form>
    </Dialog>
  )
}

type RequireSession = () => Promise<User | null>

export const useRequireSession = (
  reason: string,
): [RequireSession, JSX.Element | null] => {
  const user = useSignedInUser()
  const [{ callback }, setCallback] = useState<{
    callback?: (user: User | null) => void
  }>({})

  if (user) return [async () => user, null]

  const requireSession = () =>
    new Promise<User | null>((resolve) => {
      setCallback({
        callback: (user) => {
          setCallback({})
          resolve(user)
        },
      })
    })

  return [
    requireSession,
    <SignIn key="signin" callback={callback} reason={reason} />,
  ]
}

export default Registry.add("Dialog.SignIn", SignIn)
