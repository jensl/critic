import React, { FunctionComponent } from "react"
import clsx from "clsx"

import Registry from "."
import { makeStyles } from "@material-ui/core/styles"

const useStyles = makeStyles({
  root: {},
})

type OwnProps = {
  className?: string
}

const ReviewTags: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  return <div className={clsx(className, classes.root)} />
}

export default Registry.add("Review.Tags", ReviewTags)
