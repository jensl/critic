import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import { useSelector } from "../store"
import { useMousePosition } from "../utils/Mouse"

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
  } = useMousePosition()
  const { isRangeSelecting, boundingRect } = useSelector(
    (state) => state.ui.selectionScope,
  )
  if (!isDown || !isRangeSelecting || !boundingRect) return null
  const left = Math.max(
    Math.min(absoluteX, downAbsoluteX) + 1,
    boundingRect.left,
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
        top: top - 2,
        left: left - 2,
        width: width + 4,
        height: height + 4,
      }}
    />
  )
}

export default SelectionRectangle
