import React from "react"

import Button from "@material-ui/core/Button"

import Registry from "."
import { ActionProps } from "./Changeset.Action"
import { useChangeset } from "../utils"
import { useExpandedFiles } from "../actions/uiFileDiff"

const CollapseAll: React.FunctionComponent<ActionProps> = () => {
  const { changeset, expandedFileIDs } = useChangeset()
  const { collapseFiles } = useExpandedFiles()
  const { files } = changeset
  if (!files || files.length <= 1) return null
  return (
    <Button
      disabled={expandedFileIDs.size === 0}
      onClick={() => collapseFiles(files)}
    >
      Collapse all
    </Button>
  )
}

export default Registry.add("Changeset.Action.CollapseAll", CollapseAll)
