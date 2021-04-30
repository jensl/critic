import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."

import { useExtension } from "../utils"

const useStyles = makeStyles({
  extensionTitle: {},
})

type OwnProps = {
  className?: string
}

const ExtensionTitle: FunctionComponent<OwnProps> = () => {
  const classes = useStyles()
  const extension = useExtension()
  if (!extension) return null
  return (
    <Typography className={classes.extensionTitle} variant="h4" gutterBottom>
      {extension.key}
    </Typography>
  )
}

export default Registry.add("Extension.Title", ExtensionTitle)
