MANIFEST_FILENAMES = ("manifest.yaml", "manifest.json")


class ManifestError(Exception):
    pass


from .read import Manifest


__all__ = ["Manifest", "ManifestError", "MANIFEST_FILENAMES"]
