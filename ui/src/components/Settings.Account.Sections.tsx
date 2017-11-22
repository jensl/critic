import React from "react"

import Registry from "."
import Details from "./Settings.Account.Details"
import SSHKeys from "./Settings.Account.SSHKeys"

const Sections: React.FunctionComponent = () => (
  <>
    <Details />
    <SSHKeys />
  </>
)

export default Registry.add("Settings.Account.Sections", Sections)
