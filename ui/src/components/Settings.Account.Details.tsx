import React, { FunctionComponent } from "react"

import TextField from "@material-ui/core/TextField"

import Registry from "."
import Section from "./Settings.Account.Section"
import { setFullname } from "../actions/user"
import { useSignedInUser } from "../utils"
import { useDispatch } from "../store"

const AccountDetails: FunctionComponent = () => {
  const dispatch = useDispatch()
  const user = useSignedInUser()
  if (user === null) return null
  return (
    <Section id="details" title="Account details">
      <TextField
        label="Display name"
        defaultValue={user.fullname === user.name ? null : user.fullname}
        fullWidth
        margin="normal"
        onChange={(ev) => dispatch(setFullname(user.id, ev.target.value))}
        variant="outlined"
        helperText={`You full name, or whatever you wish to be display in place of your username ("${user.name}").`}
      />
    </Section>
  )
}

export default Registry.add("Settings.Account.Details", AccountDetails)
