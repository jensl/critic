import React, { FunctionComponent } from "react"

import Registry from "."
import Title from "./Branch.Title"

const Header: FunctionComponent = () => (
  <>
    <Title />
  </>
)

export default Registry.add("Branch.Header", Header)
