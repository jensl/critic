import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Chip from "@material-ui/core/Chip"
import Typography from "@material-ui/core/Typography"
import DoneIcon from "@material-ui/icons/Done"

import Registry from "."
import Extension from "../resources/extension"

const useStyles = makeStyles((theme) => ({
  extensionListItemTitle: {
    gridArea: "title",
  },
  chip: {
    marginLeft: theme.spacing(2),
  },
}))

type OwnProps = {
  className?: string
  extension: Extension
}

const ExtensionListItemTitle: FunctionComponent<OwnProps> = ({
  className,
  extension,
}) => {
  const classes = useStyles()
  return (
    <Typography
      className={clsx(className, classes.extensionListItemTitle)}
      variant="body1"
      component="div"
    >
      {extension.key}
      {extension.installation !== null && (
        <Chip
          className={classes.chip}
          label="Installed"
          size="small"
          color="secondary"
          onDelete={(ev) => ev.preventDefault()}
          deleteIcon={<DoneIcon />}
        />
      )}
    </Typography>
  )
}

export default Registry.add("Extension.ListItem.Title", ExtensionListItemTitle)
