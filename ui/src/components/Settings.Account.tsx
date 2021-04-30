import React, { FunctionComponent } from "react"

import Container from "@material-ui/core/Container"

import Registry from "."
import Sections from "./Settings.Account.Sections"
import { useSignedInUser } from "../utils"
import SetPrefix from "../utils/PrefixContext"

const SettingsAccount: FunctionComponent = () => {
  const user = useSignedInUser()
  if (user === null) return null
  return (
    <SetPrefix prefix="/settings/account">
      <Container maxWidth="lg">
        <Sections />
      </Container>
    </SetPrefix>
  )
}

export default Registry.add("Settings.Account", SettingsAccount)
