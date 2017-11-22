import React, { FunctionComponent } from "react"

import Registry from "."
import Appearance from "./Suggestions.Appearance"
import AccountSetup from "./Suggestions.AccountSetup"

const SuggestionsPanels: FunctionComponent = () => (
  <>
    <Appearance />
    <AccountSetup />
  </>
)

export default Registry.add("Suggestions.Panels", SuggestionsPanels)
