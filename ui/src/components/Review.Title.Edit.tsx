import React, { FunctionComponent, useEffect, useRef, useState } from "react"
import clsx from "clsx"

import { makeStyles, ThemeProvider, withStyles } from "@material-ui/core/styles"
import MuiTextField from "@material-ui/core/TextField"
import Button from "@material-ui/core/Button"

import { useReview } from "../utils"
import Registry from "."
import { useDispatch } from "../store"
import { setSummary } from "../actions/review"
import { assertNotNull } from "../debug"

const useStyles = makeStyles((theme) => ({
  reviewSummaryEdit: {
    marginBottom: "12px",
    display: "flex",
  },
}))

const TextField = withStyles((theme) => ({
  root: {
    flexGrow: 1,
    marginRight: theme.spacing(2),

    "& .MuiInput-root": {
      fontSize: "34px",
      fontWeight: "400",
      lineHeight: "1.235",
      letterSpacing: "0.00735em",
    },
    "& .MuiInput-input": {
      padding: 0,
    },
  },
}))(MuiTextField)

type Props = {
  className?: string
  onEditDone: () => void
}

const ReviewSummaryEdit: FunctionComponent<Props> = ({
  className,
  onEditDone,
}) => {
  const classes = useStyles()
  const review = useReview()
  const dispatch = useDispatch()
  const [value, setValue] = useState<string | null>(null)

  const canSave = () => value?.trim() && value !== review.summary

  const save = async (value: string | null) => {
    if (value === null) return
    await dispatch(setSummary(review.id, value))
    onEditDone()
  }

  useEffect(() => {
    if (review.summary !== null) setValue(review.summary)
  }, [review.summary])

  return (
    <div className={clsx(className, classes.reviewSummaryEdit)}>
      <TextField
        autoFocus
        value={value || ""}
        placeholder="Please provide a review summary"
        onChange={(ev) => setValue(ev.target.value)}
        onBlur={() => {
          if (!canSave()) onEditDone()
        }}
        onKeyDown={(ev) => {
          if (ev.key === "Enter") save(value)
          else if (ev.key === "Escape") onEditDone()
          else return

          ev.preventDefault()
        }}
      />
      <Button
        disabled={!canSave()}
        color="secondary"
        variant="contained"
        onClick={() => save(value)}
      >
        Save
      </Button>
    </div>
  )
}

export default Registry.add("Review.Summary.Edit", ReviewSummaryEdit)
