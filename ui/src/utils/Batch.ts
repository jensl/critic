import { useResource } from "."
import { useReview } from "./ReviewContext"

export const useUnpublished = () => {
  const review = useReview()
  return useResource("batches", ({ unpublished }) => unpublished.get(review.id))
}
