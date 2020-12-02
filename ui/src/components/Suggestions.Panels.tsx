import React, { FunctionComponent } from "react"

import Registry from "."
import Appearance from "./Suggestions.Appearance"
import AccountSetup from "./Suggestions.AccountSetup"
import CreatedBranches from "./Suggestions.CreatedBranches"

const SuggestionsPanels: FunctionComponent = () => (
  <>
    <Appearance />
    <AccountSetup />
    <CreatedBranches />
  </>
)

export default Registry.add("Suggestions.Panels", SuggestionsPanels)
