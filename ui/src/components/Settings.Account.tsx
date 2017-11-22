import React, { FunctionComponent } from "react"

import Container from "@material-ui/core/Container"

import Registry from "."
import Sections from "./Settings.Account.Sections"
import { useSignedInUser } from "../utils"

const SettingsAccount: FunctionComponent = () => {
  const user = useSignedInUser()
  if (user === null) return null
  return (
    <Container maxWidth="lg">
      <Sections />
    </Container>
  )
}

export default Registry.add("Settings.Account", SettingsAccount)
