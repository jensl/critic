import React from "react"

import Registry from "."
import RepositoryDocumentation from "./Repository.Documentation"
import Tree from "./Tree"

const RepositoryFiles: React.FunctionComponent = () => (
  <>
    <Tree />
    <RepositoryDocumentation />
  </>
)

export default Registry.add("Repository.Files", RepositoryFiles)
