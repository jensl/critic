import { UPDATE_PAGINATION_ACTION } from "../actions"
import { AsyncThunk, Dispatch, State } from "../state"
import { PaginationInfo } from "../resources/fetch"

export type PaginationThunk<T> = AsyncThunk<[T[], PaginationInfo]>

export type PaginationFetchAction<T> = (
  offset: number,
  count: number,
) => PaginationThunk<T>

export type RetrieveFn<T> = (state: State, itemIDs: number[]) => T[]

export type PaginationState<T> = {
  offset: number
  total: number
  items: T[]
}

class Pagination<T extends { id: number }> {
  constructor(
    readonly scope: string,
    readonly fetchAction: PaginationFetchAction<T>,
    readonly retrieveFn: RetrieveFn<T>,
  ) {}

  fetchRange(
    dispatch: Dispatch,
    offset: number,
    count: number,
  ): [PaginationState<T>, Promise<PaginationState<T>>] {
    const update = async (): Promise<PaginationState<T>> => {
      const [items, { total }] = await dispatch(this.fetchAction(offset, count))
      const itemIDs = items.map((item) => item.id)

      dispatch({
        type: UPDATE_PAGINATION_ACTION,
        scope: this.scope,
        offset,
        total,
        itemIDs,
      })

      return { offset, total, items }
    }

    return dispatch((_, getState) => {
      const state = getState()
      const pagination = state.ui.paginations.get(this.scope)
      const total = pagination?.total ?? 0
      let items: T[] = []
      if (pagination) {
        const itemIDs = []
        for (let index = offset; index < offset + count; ++index) {
          const itemID = pagination.itemIDs[index]
          if (itemID !== undefined) itemIDs.push(itemID)
        }
        if (itemIDs.length !== 0) items = this.retrieveFn(state, itemIDs)
      }
      return [{ offset, total, items }, update()]
    })
  }
}

export default Pagination
