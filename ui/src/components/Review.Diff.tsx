import React, { FunctionComponent } from "react"

import Registry from "."
import RepositoryDiff from "./Repository.Diff"
import SetRepository from "../utils/RepositoryContext"
import { useReview } from "../utils"
import { useSelector } from "../store"

const ReviewDiff: FunctionComponent = () => {
  const repositories = useSelector((state) => state.resource.repositories)
  const review = useReview()
  if (!review) return null
  const repository = repositories.byID.get(review.repository)
  if (!repository) return null
  return (
    <SetRepository repository={repository}>
      <RepositoryDiff />
    </SetRepository>
  )
}

export default Registry.add("Review.Diff", ReviewDiff)
