import { AsyncThunk } from "../state"
import { CommitID, RepositoryID } from "../resources/types"
import { fetchText } from "../utils/Fetch"

export const download = (
  repositoryID: RepositoryID,
  commitID: CommitID,
  path: string
): AsyncThunk<void> => async (dispatch) => {
  const response = await fetchText({
    path: "api/download",
    params: {
      repository: repositoryID,
      commit: commitID,
      path,
    },
  })

  dispatch({
    type: "DOWNLOAD",
    key: `${repositoryID}:${commitID}:${path}`,
    contents: await response.text(),
  })
}
