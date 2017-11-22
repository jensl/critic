import sys
import json


class Reject(Exception):
    pass


def update(repository_path, ref_name, old_value, new_value):
    data = json.dumps(
        {
            "repository_path": repository_path,
            "ref_name": ref_name,
            "old_value": old_value,
            "new_value": new_value,
        }
    )

    if ref_name == "refs/heads/reject-create" and old_value is None:
        raise Reject("REJECT:" + data)
    elif ref_name == "refs/heads/reject-delete" and new_value is None:
        raise Reject("REJECT:" + data)
    elif ref_name == "refs/heads/reject-update" and not (
        old_value is None or new_value is None
    ):
        raise Reject("REJECT:" + data)
    else:
        sys.stdout.write("ACCEPT:" + data + "\n")
