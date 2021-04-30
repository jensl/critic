import React, { FunctionComponent } from "react"

import Container from "@material-ui/core/Container"

import Registry from "."
import { useSignedInUser } from "../utils"
import useItemList from "../utils/ItemList"
import Basic from "./Settings.System.Basic"
import { WithExtension } from "../utils/ExtensionContext"
import { WithCritic } from "../extension"
import SetPrefix from "../utils/PrefixContext"

const SettingsSystem: FunctionComponent = () => {
  const user = useSignedInUser()
  const items = useItemList("system-settings-panels", { basic: Basic })
  if (user === null) return null
  return (
    <SetPrefix prefix="/settings/system">
      <Container maxWidth="lg">
        {items.map(([id, Component, extension]) =>
          extension === null ? (
            <Component key={id} />
          ) : extension ? (
            <WithCritic key={id} extension={extension}>
              <Component />
            </WithCritic>
          ) : null,
        )}
      </Container>
    </SetPrefix>
  )
}

export default Registry.add("Settings.System", SettingsSystem)
