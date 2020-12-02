import os

from .error import ManifestError
from .role import Role


class UIAddonRole(Role, role_type="uiaddon"):
    name = "UIAddon"
    table_names = {"extensionuiaddonroles"}
    does_execute = False

    def __init__(self, name, bundle_js, bundle_css):
        self.name = name
        self.bundle_js = bundle_js
        self.bundle_css = bundle_css

    async def install_specific(self, cursor, role_id):
        await cursor.execute(
            """INSERT INTO extensionuiaddonroles (
                        role, name, bundle_js, bundle_css
                      )
               VALUES ({role}, {name}, {bundle_js}, {bundle_css})""",
            role=role_id,
            name=self.name,
            bundle_js=self.bundle_js,
            bundle_css=self.bundle_css,
        )

    def check(self, manifest):
        if manifest.path is not None:
            bundle_js_path = os.path.join(manifest.path, self.bundle_js)
            if not os.path.isfile(bundle_js_path):
                raise ManifestError("%s: no such file" % self.bundle_js)
            if self.bundle_css:
                bundle_css_path = os.path.join(manifest.path, self.bundle_css)
                if not os.path.isfile(bundle_css_path):
                    raise ManifestError("%s: no such file" % self.bundle_css)
