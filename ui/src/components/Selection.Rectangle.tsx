import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import { useSelector } from "../store"

const useStyles = makeStyles((theme) => ({
  root: { position: "absolute", ...theme.critic.selectionRectangle },
}))

type Props = {
  className?: string
}

const SelectionRectangle: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const {
    isDown,
    absoluteX,
    absoluteY,
    downAbsoluteX,
    downAbsoluteY,
  } = useSelector((state) => state.ui.mouse)
  const { isRangeSelecting, boundingRect } = useSelector(
    (state) => state.ui.selectionScope
  )
  if (!isDown || !isRangeSelecting || !boundingRect) return null
  const left = Math.max(
    Math.min(absoluteX, downAbsoluteX) + 1,
    boundingRect.left
  )
  const width =
    Math.min(Math.max(absoluteX, downAbsoluteX), boundingRect.right) - left - 1
  const top = Math.max(Math.min(absoluteY, downAbsoluteY), boundingRect.top) + 1
  const height =
    Math.min(Math.max(absoluteY, downAbsoluteY), boundingRect.bottom) - top - 1
  return (
    <div
      className={clsx(className, classes.root)}
      style={{
        left,
        width,
        top,
        height,
      }}
    />
  )
}

export default SelectionRectangle
