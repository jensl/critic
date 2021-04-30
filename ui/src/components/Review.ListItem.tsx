import React, { FunctionComponent } from "react"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Progress from "./Review.ListItem.Progress"
import Title from "./Review.ListItem.Title"
import Metadata from "./Review.ListItem.Metadata"
import { ReviewID } from "../resources/types"
import { usePrefix, useResource } from "../utils"

const useStyles = makeStyles((theme) => ({
  reviewListItem: {
    display: "grid",
    paddingTop: theme.spacing(1),
    paddingBottom: theme.spacing(1),
    [theme.breakpoints.up("md")]: {
      gridTemplateRows: "1fr 1fr",
      gridTemplateColumns: "4rem 1fr",
      gridTemplateAreas: `
        "progress title"
        "progress metadata"
      `,
      paddingLeft: theme.spacing(2),
      paddingRight: theme.spacing(2),
    },
    [theme.breakpoints.down("sm")]: {
      gridTemplateRows: "auto",
      gridTemplateColumns: "1fr",
      gridTemplateAreas: `
        "title"
        "metadata"
      `,
      paddingLeft: theme.spacing(0.5),
      paddingRight: theme.spacing(0.5),
    },
    textDecoration: "none",
    color: "inherit",

    "&:hover": {
      background: theme.palette.secondary.light,
      cursor: "pointer",
      borderRadius: 4,
    },
  },
}))

type OwnProps = {
  className?: string
  reviewID: ReviewID
}

const ReviewListItem: FunctionComponent<OwnProps> = ({
  className,
  reviewID,
}) => {
  const classes = useStyles()
  const prefix = usePrefix()
  const review = useResource("reviews", (byID) => byID.get(reviewID))
  if (!review) return null
  return (
    <Link
      to={`${prefix}/review/${reviewID}`}
      className={clsx(className, classes.reviewListItem)}
    >
      <Progress review={review} />
      <Title review={review} />
      <Metadata review={review} />
    </Link>
  )
}

export default Registry.add("Review.ListItem", ReviewListItem)
