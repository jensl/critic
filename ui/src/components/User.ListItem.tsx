import React from "react"

import Registry from "."
import UserChip from "./User.Chip"

// FIXME: In the future, make the child type (plain name, chip, avatar, et c.)
// configurable. Probably with a context identifier so that it can be
// different in different contexts.
const UserListItem = (props: any) => <UserChip {...props} />

export default Registry.add("User.ListItem", UserListItem)
