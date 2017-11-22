import React from "react"

import Registry from "."
import BranchCommits from "./Branch.Commits"
import { useBranch, useRepository } from "../utils"

type Props = {
  className?: string
}

const RepositoryBranchCommits: React.FunctionComponent<Props> = ({
  className,
}) => {
  const branch = useBranch()
  const repository = useRepository()
  if (!branch || !repository) return null
  return (
    <BranchCommits
      pathPrefix={`/repository/${repository.name}`}
      className={className}
      branch={branch}
    />
  )
}

export default Registry.add(
  "Repository.Branch.Commits",
  RepositoryBranchCommits
)
