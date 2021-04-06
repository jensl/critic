import React, { FunctionComponent } from "react"
import clsx from "clsx"

import Chip from "@material-ui/core/Chip"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { map, useResource, useReview } from "../utils"

const useStyles = makeStyles((theme) => ({
  root: {
    marginBottom: theme.spacing(1),

    "& > *": {
      marginRight: theme.spacing(1),
    },
  },
}))

type OwnProps = {
  className?: string
}

const ReviewTags: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  const reviewTagByID = useResource("reviewtags", ({ byID }) => byID)
  const review = useReview()
  return (
    <div className={clsx(className, classes.root)}>
      {map(review.tags, (tagID) => reviewTagByID.get(tagID)).map((tag) =>
        tag ? <Chip key={tag.id} label={tag.name} size="small" /> : null,
      )}
    </div>
  )
}

export default Registry.add("Review.Tags", ReviewTags)
