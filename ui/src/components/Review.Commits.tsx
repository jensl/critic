import React, { FunctionComponent } from "react"

import Registry from "."
import Partition from "./Review.Commits.Partition"
import { useReview } from "../utils"

const ReviewCommits: FunctionComponent<{}> = () => {
  const review = useReview()
  if (!review) return null
  return (
    <>
      {review.partitions.map((partition, index) => (
        <Partition key={index} index={index} partition={partition} />
      ))}
    </>
  )
}

export default Registry.add("Review.Commits", ReviewCommits)
