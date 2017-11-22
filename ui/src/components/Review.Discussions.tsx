import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."

const useStyles = makeStyles({
  ReviewDiscussions: {},
})

type OwnProps = {
  className?: string
}

const ReviewDiscussions: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  return <div className={clsx(className, classes.ReviewDiscussions)} />
}

export default Registry.add("Review.Discussions", ReviewDiscussions)
