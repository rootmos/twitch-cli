import os

import importlib.metadata
import importlib.resources
import importlib.resources.abc

package_name = __name__
package_version = importlib.metadata.version(package_name)

def package_data(*f) -> importlib.resources.abc.Traversable:
    return importlib.resources.files(package_name).joinpath(*f)

whoami = importlib.metadata.metadata(__name__).get("name")
assert whoami is not None
env_prefix = whoami.upper().replace("-", "_").replace(".", "_") + "_"
def env(var, default=None):
    return os.environ.get(env_prefix + var, default)
