import React, { useState } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import IconButton from "@material-ui/core/IconButton"
import MoreVertIcon from "@material-ui/icons/MoreVert"
import Menu from "@material-ui/core/Menu"
import MenuItem from "@material-ui/core/MenuItem"

import Registry from "."
import PrimaryActions from "./Review.Actions.Primary"

const useStyles = makeStyles((theme) => ({
  reviewActions: {
    margin: "1rem",
    display: "flex",
    flexDirection: "row",
    justifyContent: "flex-end",
    alignItems: "center",
  },
  moreButton: {},
}))

type Props = {
  className?: string
}

const ReviewActions: React.FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const [anchorEl, setAnchorEl] = useState<Element | null>(null)
  return (
    <div className={clsx(className, classes.reviewActions)}>
      <PrimaryActions />
      <IconButton
        className={classes.moreButton}
        onClick={(ev) => setAnchorEl(ev.target as Element)}
      >
        <MoreVertIcon />
      </IconButton>
      <Menu
        anchorEl={anchorEl}
        open={anchorEl !== null}
        onClose={() => setAnchorEl(null)}
      >
        <MenuItem>Drop review</MenuItem>
      </Menu>
    </div>
  )
}

export default Registry.add("Review.Actions", ReviewActions)
