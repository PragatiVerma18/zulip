import hashlib
import json
import os
import shutil
import subprocess

import yaml

from .zulip_tools import parse_os_release, run

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ZULIP_SRV_PATH = "/srv"

PUPPET_MODULES_CACHE_PATH = os.path.join(ZULIP_SRV_PATH, "zulip-puppet-cache")
PUPPET_DEPS_FILE_PATH = os.path.join(ZULIP_PATH, "puppet/deps.yaml")
PUPPET_THIRDPARTY = os.path.join(PUPPET_MODULES_CACHE_PATH, "current")


def generate_sha1sum_puppet_modules() -> str:
    data = {}
    with open(PUPPET_DEPS_FILE_PATH, "r") as fb:
        data["deps.yaml"] = fb.read().strip()
    data["puppet-version"] = subprocess.check_output(
        # This is 10x faster than `puppet --version`
        ["ruby", "-r", "puppet/version", "-e", "puts Puppet.version"],
        universal_newlines=True,
    ).strip()

    sha1sum = hashlib.sha1()
    sha1sum.update(json.dumps(data, sort_keys=True).encode("utf-8"))
    return sha1sum.hexdigest()


def setup_puppet_modules() -> None:
    sha1sum = generate_sha1sum_puppet_modules()
    target_path = os.path.join(PUPPET_MODULES_CACHE_PATH, sha1sum)
    success_stamp = os.path.join(target_path, ".success-stamp")
    # Check if a cached version already exists
    if not os.path.exists(success_stamp):
        do_puppet_module_install(target_path, success_stamp)

    if os.path.islink(PUPPET_THIRDPARTY):
        os.remove(PUPPET_THIRDPARTY)
    elif os.path.isdir(PUPPET_THIRDPARTY):
        shutil.rmtree(PUPPET_THIRDPARTY)
    os.symlink(target_path, PUPPET_THIRDPARTY)


def do_puppet_module_install(
    target_path: str,
    success_stamp: str,
) -> None:
    # This is to suppress Puppet warnings with ruby 2.7.
    distro_info = parse_os_release()
    puppet_env = os.environ.copy()
    if (distro_info["ID"], distro_info["VERSION_ID"]) in [("ubuntu", "20.04")]:
        puppet_env["RUBYOPT"] = "-W0"

    os.makedirs(target_path, exist_ok=True)
    with open(PUPPET_DEPS_FILE_PATH, "r") as yaml_file:
        deps = yaml.safe_load(yaml_file)
        for module, version in deps.items():
            run(
                [
                    "puppet",
                    "module",
                    "--modulepath",
                    target_path,
                    "install",
                    module,
                    "--version",
                    version,
                ],
                env=puppet_env,
            )
    with open(success_stamp, "w"):
        pass
