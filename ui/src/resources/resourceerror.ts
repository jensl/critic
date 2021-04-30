export type ErrorResponseJSON = {
  error: { title: string; message: string; code: string }
}

class ResourceError extends Error {
  readonly title: string
  readonly code: string

  constructor(
    readonly status: number,
    { error: { title, message, code } }: ErrorResponseJSON,
  ) {
    super(message)
    this.title = title
    this.message = message
    this.code = code
  }
}

export default ResourceError
