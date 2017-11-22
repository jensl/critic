# @dependency 004-repositories/003-small.py

import textwrap

NONSENSE = """
Lorem ipsum dolor sit amet, consectetur adipiscing
elit. Donec ut enim sit amet purus ultricies
lobortis. Pellentesque nisi arcu, convallis sed purus sed,
semper ultrices velit. Ut egestas lorem tortor, vitae
lacinia lorem consectetur nec. Integer tempor ornare ipsum
at viverra. Curabitur nec orci mollis, lacinia sapien eget,
ultricies ipsum. Curabitur a libero tortor. Curabitur
volutpat lacinia erat, ac suscipit enim dignissim nec.
"""


def content(*versions):
    return (
        "\n\n".join(
            textwrap.indent(NONSENSE, f"[{version}] ").strip() for version in versions
        )
        + "\n"
    )
