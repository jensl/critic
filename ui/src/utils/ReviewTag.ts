import { map, useResource, useReview } from "."

export const useReviewTags = (): Set<string> => {
  const review = useReview()
  const tagsByID = useResource("reviewtags", ({ byID }) => byID)
  return new Set<string>(
    map(review.tags, (tagID) => tagsByID.get(tagID)?.name).filter(
      (name) => !!name,
    ) as string[],
  )
}
