import React, { FunctionComponent } from "react"

import Registry from "."
import Breadcrumb from "./Breadcrumb"
import { useRepository, usePrefix } from "../utils"
import ReviewContext from "./Review.Context"

const RepositoryReview: FunctionComponent = () => {
  const repository = useRepository()
  const prefix = usePrefix()
  if (!repository) return null
  return (
    <Breadcrumb label="reviews" path={`${prefix}/reviews`}>
      <ReviewContext />
    </Breadcrumb>
  )
}

export default Registry.add("Repository.Review", RepositoryReview)
