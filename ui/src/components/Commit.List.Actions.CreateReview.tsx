import React, { FunctionComponent } from "react"
import { useHistory } from "react-router"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Button from "@material-ui/core/Button"

import Registry from "."
import { createReview } from "../actions/review"
import { resetSelectionScope } from "../actions/uiSelectionScope"
import { useRepository, useReview, useSignedInUser } from "../utils"
import { ActionProps } from "./Commit.List.Actions.types"
import { useDispatch } from "../store"

const useStyles = makeStyles({
  commitListActionsCreateReview: {},
})

type Props = {
  className?: string
}

const CreateReview: FunctionComponent<ActionProps & Props> = ({
  className,
  selectedCommits,
}) => {
  const classes = useStyles()
  const history = useHistory()
  const dispatch = useDispatch()
  const repository = useRepository()
  const review = useReview()
  const signedInUser = useSignedInUser()
  if (repository === null) return null
  if (review !== null) return null
  const onClick = () =>
    dispatch(
      createReview(
        repository.id,
        selectedCommits.map((commit) => commit.id).toArray()
      )
    ).then((review) => {
      dispatch(resetSelectionScope())
      if (review) history.push(`/review/${review.id}`)
    })
  return (
    <Button
      className={clsx(className, classes.commitListActionsCreateReview)}
      onClick={onClick}
      disabled={signedInUser === null}
    >
      Create review
    </Button>
  )
}

export default Registry.add("Commit.List.Actions.CreateReview", CreateReview)
