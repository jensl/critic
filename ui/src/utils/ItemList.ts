import React from "react"
import { map, sortedBy, useResource } from "."

import { ItemList } from "../actions"
import Extension from "../resources/extension"
import { useSelector } from "../store"

interface BaseItems {
  [id: string]: React.FunctionComponent<{}>
}

type Item = [string, React.FunctionComponent<{}>, Extension | null | undefined]

const useItemList = (list: ItemList, baseItems: BaseItems): Item[] => {
  const extensions = useResource("extensions", ({ byID }) => byID)
  const extraItems = useSelector(
    (state) => state.ui.itemLists.get("system-settings-panels") || [],
  )
  const items: Item[] = map(
    Object.entries(baseItems),
    ([id, render]): Item => [id, render, null],
  )
  for (const extraItem of sortedBy(extraItems, (item) => item.itemID)) {
    const item: Item = [
      extraItem.itemID,
      extraItem.render,
      extensions.get(extraItem.extensionID),
    ]
    if (extraItem.before) {
      const index = items.findIndex(([itemId]) => itemId === extraItem.before)
      if (index === -1) {
        console.warn(
          `Item list [${list}]: item [${extraItem.itemID}] to be added before` +
            ` item [${extraItem.before}], which did not exist`,
        )
        items.push(item)
      } else items.splice(index, 0, item)
    } else if (extraItem.after) {
      const index = items.findIndex(([itemId]) => itemId === extraItem.after)
      if (index === -1) {
        console.warn(
          `Item list [${list}]: item [${extraItem.itemID}] to be added after` +
            ` item [${extraItem.after}], which did not exist`,
        )
        items.push(item)
      } else items.splice(index + 1, 0, item)
    } else items.push(item)
  }
  return items
}

export default useItemList
