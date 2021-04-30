import React, { FunctionComponent } from "react"
import Comment from "../resources/comment"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Discussion from "./Discussion"
import { Location } from "../actions/comment"

const useStyles = makeStyles((theme) => ({
  changesetComment: {
    padding: theme.spacing(0.5, 2),
  },
}))

type OwnProps = {
  className?: string
  comment?: Comment
  location?: Location | null
}

const ChangesetComment: FunctionComponent<OwnProps> = ({
  className,
  comment,
  location,
}) => {
  const classes = useStyles()
  return (
    <div className={clsx(className, classes.changesetComment)}>
      <Discussion comment={comment} location={location ?? null} />
    </div>
  )
}

export default Registry.add("Changeset.Comment", ChangesetComment)
