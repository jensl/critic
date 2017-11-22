import React, { useContext } from "react"

import Flag from "./Flag"
import Value from "./Value"
import { Location } from "../actions/comment"
import Comment from "../resources/comment"
import Reply from "../resources/reply"

type Props = {
  comment: Comment | null
  replies: Reply[] | null
  draftReply: Reply | null
  currentText: Value<string> | null
  editable: Flag | null
  location: Location | null
}

const DiscussionContext = React.createContext<Props>({
  comment: null,
  replies: null,
  draftReply: null,
  currentText: null,
  editable: null,
  location: null,
})

export const useDiscussionContext = () => useContext(DiscussionContext)

export const SetDiscussionContext: React.FunctionComponent<Props> = ({
  children,
  ...props
}) => (
  <DiscussionContext.Provider value={props}>
    {children}
  </DiscussionContext.Provider>
)
