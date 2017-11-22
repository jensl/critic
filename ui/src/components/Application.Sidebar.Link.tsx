import React, { useContext, FunctionComponent } from "react"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles, withStyles } from "@material-ui/core/styles"
import ListItem from "@material-ui/core/ListItem"
import ListItemIcon from "@material-ui/core/ListItemIcon"
import ListItemText from "@material-ui/core/ListItemText"
import MUIBadge from "@material-ui/core/Badge"

import Registry from "."
import { SidebarContext } from "../utils"

const useStyles = makeStyles((theme) => ({
  applicationSidebarLink: {},
  indent: {
    paddingLeft: theme.spacing(4),
  },
}))

type BadgeProps = {
  badgeContent: number | null
  color?: "default" | "primary" | "secondary" | "error"
}

type OwnProps = {
  className?: string
  href: string
  icon?: JSX.Element
  badge?: BadgeProps
  text: string
}

const Badge = withStyles((theme) => ({
  badge: { top: "50%", right: -theme.spacing(3) },
}))(MUIBadge)

const ApplicationSidebarLink: FunctionComponent<OwnProps> = ({
  className,
  href,
  icon,
  badge,
  text,
}) => {
  const classes = useStyles()
  const { hideIfTemporary } = useContext(SidebarContext)
  let content
  if (badge) content = <Badge {...badge}>{text}</Badge>
  else content = text
  return (
    <ListItem
      className={clsx(className, classes.applicationSidebarLink, {
        [classes.indent]: !icon,
      })}
      button
      component={Link}
      to={href}
      onClick={hideIfTemporary}
    >
      {icon && <ListItemIcon>{icon}</ListItemIcon>}
      <ListItemText primary={content} />
    </ListItem>
  )
}

export default Registry.add("Application.Sidebar.Link", ApplicationSidebarLink)
