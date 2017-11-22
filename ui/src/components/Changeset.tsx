import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import ChangesetFiles from "./Changeset.Files"

const useStyles = makeStyles({
  changeset: {},
})

type Props = {
  className?: string
  variant?: "unified" | "side-by-side"
}

const Changeset: FunctionComponent<Props> = ({ className, variant }) => {
  const classes = useStyles()
  return (
    <div className={clsx(className, classes.changeset)}>
      <ChangesetFiles variant={variant} />
    </div>
  )
}

export default Registry.add("Changeset", Changeset)
