import React, { FunctionComponent } from "react"
import { useHistory } from "react-router"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Breadcrumbs from "@material-ui/core/Breadcrumbs"
import Container from "@material-ui/core/Container"
import NavigateNextIcon from "@material-ui/icons/NavigateNext"

import Registry from "."
import Breadcrumb from "./Application.Breadcrumb"
import { useSelector } from "../store"
import { ShortcutScope } from "../utils/KeyboardShortcuts"

const useStyles = makeStyles((theme) => ({
  applicationBreadcrumbs: {
    marginTop: -theme.spacing(1),
    marginBottom: theme.spacing(2),
  },
}))

type Props = {
  className?: string
}

const ApplicationBreadcrumbs: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const history = useHistory()
  const breadcrumbs = useSelector((state) => state.ui.rest.breadcrumbs)
  if (breadcrumbs.size === 0) return null
  const items = breadcrumbs.map(({ category, label, path }) => (
    <Breadcrumb key={label} category={category} label={label} path={path} />
  ))

  const popLast = () => {
    console.log("popLast", { breadcrumbs, items })
    if (breadcrumbs.size >= 2) {
      const path = breadcrumbs.get(breadcrumbs.size - 2)?.path
      if (path) history.push(path)
    }
  }

  console.log({ items })

  return (
    <ShortcutScope name="breadcrumbs" handler={{ u: popLast }}>
      <Container
        maxWidth="lg"
        className={clsx(className, classes.applicationBreadcrumbs)}
      >
        <Breadcrumbs separator={<NavigateNextIcon fontSize="small" />}>
          {items}
        </Breadcrumbs>
      </Container>
    </ShortcutScope>
  )
}

export default Registry.add("Application.Breadcrumbs", ApplicationBreadcrumbs)
