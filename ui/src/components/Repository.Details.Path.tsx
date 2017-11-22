import React, { FunctionComponent } from "react"

import Registry from "."
import DetailsRow from "./Details.Row"
import { useRepository } from "../utils"

const RepositoryDetailsBranch: FunctionComponent = () => {
  const repository = useRepository()
  if (!repository) return null
  return <DetailsRow heading="Path">{repository.path}</DetailsRow>
}

export default Registry.add(
  "Repository.Details.Branch",
  RepositoryDetailsBranch
)
