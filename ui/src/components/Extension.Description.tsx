import React, { FunctionComponent } from "react"

import Container from "@material-ui/core/Container"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import MarkdownDocument from "./Markdown.Document"
import { useExtensionVersion } from "../utils/ExtensionContext"

const useStyles = makeStyles({
  extensionDescription: {},
})

type OwnProps = {
  className?: string
}

const ExtensionDescription: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  const version = useExtensionVersion()
  if (!version) return null
  return (
    <Container className={className} maxWidth="md">
      <MarkdownDocument source={version.description} />
    </Container>
  )
}

export default Registry.add("Extension.Description", ExtensionDescription)
