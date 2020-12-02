import React, { FunctionComponent } from "react"

import Registry from "."
import { useResource } from "../utils"
import { RepositoryID } from "../resources/types"
import Reference from "./Reference"

type Props = {
  className?: string
  repositoryID: RepositoryID
  link?: boolean
}

const RepositoryPath: FunctionComponent<Props> = ({
  className,
  repositoryID,
  link = false,
}) => {
  const repository = useResource("repositories", ({ byID }) =>
    byID.get(repositoryID),
  )
  if (!repository) return null
  return (
    <Reference
      className={className}
      linkTo={link ? `/repository/${repository.name}` : undefined}
    >
      {repository.path}
    </Reference>
  )
}

export default Registry.add("Repository.Path", RepositoryPath)
