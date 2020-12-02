import React from "react"

import Button from "@material-ui/core/Button"

import Registry from "."
import { ActionProps } from "./Changeset.Action"
import { useChangeset } from "../utils"
import { useExpandedFiles } from "../actions/uiFileDiff"

const ExpandAll: React.FunctionComponent<ActionProps> = () => {
  const { changeset, expandedFileIDs } = useChangeset()
  const { expandFiles } = useExpandedFiles()
  const { files } = changeset
  if (!files || files.length <= 1) return null
  return (
    <Button
      disabled={files.length === expandedFileIDs.size}
      onClick={() => expandFiles(files)}
    >
      Expand all
    </Button>
  )
}

export default Registry.add("Changeset.Action.ExpandAll", ExpandAll)
