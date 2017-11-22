import React, { FunctionComponent } from "react"

import Registry from "."
import RepositoryListItem from "./Repository.ListItem"
import { RepositoryID } from "../resources/types"
import { map } from "../utils"

type OwnProps = {
  repositoryIDs: Iterable<RepositoryID>
}

const RepositoryList: FunctionComponent<OwnProps> = ({ repositoryIDs }) => (
  <>
    {map(repositoryIDs, (repositoryID) => (
      <RepositoryListItem key={repositoryID} repositoryID={repositoryID} />
    ))}
  </>
)

export default Registry.add("Repository.List", RepositoryList)
