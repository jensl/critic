import React, { FunctionComponent } from "react"

import Registry from "."
import ExtensionTitle from "./Extension.Title"

const ExtensionHeader: FunctionComponent = () => (
  <>
    <ExtensionTitle />
  </>
)

export default Registry.add("Extension.Header", ExtensionHeader)
