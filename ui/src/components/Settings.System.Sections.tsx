import React from "react"

import Registry from "."
import Basic from "./Settings.System.Basic"

const Sections: React.FunctionComponent = () => (
  <>
    <Basic />
  </>
)

export default Registry.add("Settings.System.Sections", Sections)
