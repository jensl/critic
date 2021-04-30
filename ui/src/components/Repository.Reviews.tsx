import React, { useEffect, useState } from "react"

import Registry from "."
import ReviewList from "./Review.List"
import { loadRepositoryReviews } from "../actions/review"
import { ReviewID } from "../resources/types"
import { useDispatch } from "../store"
import { useRepository } from "../utils"
import Breadcrumb from "./Breadcrumb"
import SetPrefix from "../utils/PrefixContext"

const RepositoryReviews: React.FunctionComponent = () => {
  const dispatch = useDispatch()
  const repository = useRepository()
  const [reviewIDs, setReviewIDs] = useState<ReviewID[]>([])
  const [offset] = useState(0)
  const count = 25

  useEffect(() => {
    if (repository)
      dispatch(
        loadRepositoryReviews(repository.id, offset, count),
      ).then((reviews) => setReviewIDs(reviews.map((review) => review.id)))
  }, [dispatch, repository?.id, offset, count])

  if (!repository) return null

  return (
    <Breadcrumb label="reviews">
      <SetPrefix prefix={`/repository/${repository.name}`}>
        <ReviewList reviewIDs={reviewIDs} />
      </SetPrefix>
    </Breadcrumb>
  )
}

export default Registry.add("Repository.Reviews", RepositoryReviews)
