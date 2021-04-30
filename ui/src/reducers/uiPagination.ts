import produce from "./immer"
import { UPDATE_PAGINATION_ACTION } from "../actions"

export type Pagination = {
  total: number
  itemIDs: readonly number[]
}

const paginations = produce<ReadonlyMap<string, Pagination>>(
  (draft, action) => {
    if (action.type === UPDATE_PAGINATION_ACTION) {
      const { offset, total, itemIDs } = action
      let pagination = draft.get(action.scope)
      if (!pagination) {
        pagination = { total, itemIDs: [] }
        draft.set(action.scope, pagination)
      }
      pagination.total = total
      const paginationItemIDs = pagination.itemIDs
      itemIDs.forEach((itemID, index) => {
        paginationItemIDs[offset + index] = itemID
      })
    }
  },
  new Map(),
)

export default paginations
