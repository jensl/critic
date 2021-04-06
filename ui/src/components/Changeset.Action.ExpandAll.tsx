import React from "react"

import Button from "@material-ui/core/Button"

import Registry from "."
import { ActionProps } from "./Changeset.Action"
import { useChangeset } from "../utils"
import { useExpandedFiles } from "../actions/uiFileDiff"
import { ShortcutScope } from "../utils/KeyboardShortcuts"

const ExpandAll: React.FunctionComponent<ActionProps> = () => {
  const { changeset, expandedFileIDs } = useChangeset()
  const { expandFiles } = useExpandedFiles()
  const { files } = changeset
  if (!files || files.length <= 1) return null
  const disabled = files.length === expandedFileIDs.size
  const onClick = () => expandFiles(files)
  return (
    <ShortcutScope
      name="ShowDiff"
      handler={{ e: onClick }}
      component={Button}
      componentProps={{
        disabled,
        onClick,
      }}
    >
      Expand all
    </ShortcutScope>
  )
}

export default Registry.add("Changeset.Action.ExpandAll", ExpandAll)
