import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import UserName from "./User.Name"
import { useResource } from "../utils"

const useStyles = makeStyles((theme) => ({
  reviewCommitsRebase: {
    display: "flex",
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    padding: `${theme.spacing(1)}px ${theme.spacing(2)}px`,
    fontWeight: 700,
    //display: "inline-block",
    //width: "50%",
    //marginLeft: "auto",
    //marginRight: "auto",
  },
}))

type Props = {
  className?: string
  rebaseID: number
}

const ReviewCommitsRebase: FunctionComponent<Props> = ({
  className,
  rebaseID,
}) => {
  const classes = useStyles()
  const rebase = useResource("rebases", (rebases) => rebases.get(rebaseID))
  if (!rebase) return null
  return (
    <div className={clsx(className, classes.reviewCommitsRebase)}>
      <span>
        {rebase.type === "history-rewrite"
          ? "History rewritten by "
          : "Branch rebased by "}
        <UserName userID={rebase.creator} />
      </span>
    </div>
  )
}

export default Registry.add("Review.Commits.Rebase", ReviewCommitsRebase)
