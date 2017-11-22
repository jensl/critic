import React, { FunctionComponent } from "react"

import Registry from "."
import RepositoryTitle from "./Repository.Title"

const RepositoryHeader: FunctionComponent = () => (
  <>
    <RepositoryTitle />
  </>
)

export default Registry.add("Repository.Header", RepositoryHeader)
