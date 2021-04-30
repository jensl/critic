import React, { FunctionComponent } from "react"
import { useLocation } from "react-router"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."

const useStyles = makeStyles({
  applicationBreadcrumb: {},
  link: {
    textDecoration: "none",
    color: "inherit",
    "&:hover": {
      textDecoration: "underline",
    },
  },
  category: { display: "inline" },
  label: { display: "inline" },
})

type OwnProps = {
  className?: string
  category: string | null
  label: string
  path: string | null
}

const ApplicationBreadcrumb: FunctionComponent<OwnProps> = ({
  className,
  category,
  label,
  path,
}) => {
  const classes = useStyles()
  const location = useLocation()
  const content = (
    <>
      {category && (
        <Typography className={classes.category} variant="caption">
          {category}
          {": "}
        </Typography>
      )}
      <Typography className={classes.label} variant="body1">
        {label}
      </Typography>
    </>
  )
  if (path === null || path === location.pathname)
    return (
      <div className={clsx(className, classes.applicationBreadcrumb)}>
        {content}
      </div>
    )
  return (
    <Link
      to={path}
      className={clsx(className, classes.applicationBreadcrumb, classes.link)}
    >
      {content}
    </Link>
  )
}

export default Registry.add("Application.Breadcrumb", ApplicationBreadcrumb)
