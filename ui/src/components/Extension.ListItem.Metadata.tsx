import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Extension from "../resources/extension"
import MarkdownDocument from "./Markdown.Document"
import { useDeducedVersion } from "../utils/Extension"

const useStyles = makeStyles({
  extensionListItemMetadata: {
    gridArea: "metadata",
    opacity: 0.5,
  },
})

type OwnProps = {
  className?: string
  extension: Extension
}

const ExtensionListItemMetadata: FunctionComponent<OwnProps> = ({
  className,
  extension,
}) => {
  const classes = useStyles()
  const version = useDeducedVersion(extension)
  if (!version) return null
  return (
    <div className={clsx(className, classes.extensionListItemMetadata)}>
      <MarkdownDocument source={version.description} summary />
    </div>
  )
}

export default Registry.add(
  "Extension.ListItem.Metadata",
  ExtensionListItemMetadata,
)
