import os

import importlib.resources
import importlib.metadata

package_name = __name__
package_version = importlib.metadata.version(package_name)

def package_data(*f):
    return importlib.resources.files(package_name).joinpath(*f)

whoami = __name__
env_prefix = whoami.upper().replace("-", "_").replace(".", "_") + "_"
def env(var, default=None):
    return os.environ.get(env_prefix + var, default)
