import React, { FunctionComponent } from "react"
import { useLocation } from "react-router"

import LoaderBlock from "./Loader.Block"
import { SetChangeset } from "../utils/ChangesetContext"
import { parseExpandedFiles } from "../utils/Changeset"
import Changeset from "../resources/changeset"

interface Props {
  changeset: Changeset | null
}

const ChangesetContext: FunctionComponent<Props> = ({
  changeset,
  children,
}) => {
  const location = useLocation()
  const expandedFileIDs = parseExpandedFiles(location)
  if (changeset === null) return <LoaderBlock waitingFor="Changeset" />
  return (
    <SetChangeset changeset={changeset} expandedFileIDs={expandedFileIDs}>
      {children}
    </SetChangeset>
  )
}

export default ChangesetContext
