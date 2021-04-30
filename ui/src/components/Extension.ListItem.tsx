import React, { FunctionComponent } from "react"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Title from "./Extension.ListItem.Title"
import Metadata from "./Extension.ListItem.Metadata"
import { ExtensionID } from "../resources/types"
import { useResource } from "../utils"

const useStyles = makeStyles((theme) => ({
  extensionListItem: {
    display: "grid",
    paddingTop: theme.spacing(1),
    paddingBottom: theme.spacing(1),
    [theme.breakpoints.up("md")]: {
      gridTemplateRows: "auto",
      gridTemplateColumns: "4rem 1fr",
      gridTemplateAreas: `
        "progress title"
        "progress metadata"
      `,
      paddingLeft: theme.spacing(2),
      paddingRight: theme.spacing(2),
    },
    [theme.breakpoints.down("sm")]: {
      gridTemplateRows: "auto",
      gridTemplateColumns: "1fr",
      gridTemplateAreas: `
        "title"
        "metadata"
      `,
      paddingLeft: theme.spacing(0.5),
      paddingRight: theme.spacing(0.5),
    },
    textDecoration: "none",
    color: "inherit",

    "&:hover": {
      background: theme.palette.secondary.light,
      cursor: "pointer",
      borderRadius: 4,
    },
  },
}))

type OwnProps = {
  className?: string
  extensionID: ExtensionID
}

const ExtensionListItem: FunctionComponent<OwnProps> = ({
  className,
  extensionID,
}) => {
  const classes = useStyles()
  const extension = useResource("extensions").byID.get(extensionID)
  if (!extension) return null
  return (
    <Link
      to={`/extension/${extension.name}`}
      className={clsx(className, classes.extensionListItem)}
    >
      <Title extension={extension} />
      <Metadata extension={extension} />
    </Link>
  )
}

export default Registry.add("Extension.ListItem", ExtensionListItem)
