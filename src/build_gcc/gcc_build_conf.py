import os
import time
import logging

import sys_detection

from typing import Optional

from build_gcc.helpers import (
    get_current_timestamp_str,
    get_major_version,
)
from build_gcc.constants import (
    BUILD_DIR_SUFFIX_WITH_SEPARATOR,
    YB_GCC_ARCHIVE_NAME_PREFIX,
    GIT_SHA1_PLACEHOLDER_STR,
    NAME_COMPONENT_SEPARATOR,
    GCC_CLONE_REL_PATH,
    GIT_SHA1_PREFIX_LENGTH,
)


class GCCBuildConf:
    install_parent_dir: str
    version: str
    gcc_major_version: int
    user_specified_suffix: Optional[str]
    skip_auto_suffix: bool
    git_sha1_prefix: Optional[str]

    # Whether to delete build directory before the build.
    clean_build: bool

    # A timestamp string for when this confugration was created.
    build_start_timestamp_str: str

    unix_timestamp_for_suffix: Optional[str]

    tag_override: Optional[str]

    parallelism: Optional[int]

    target_arch: str

    def __init__(
            self,
            install_parent_dir: str,
            version: str,
            user_specified_suffix: Optional[str],
            skip_auto_suffix: bool,
            clean_build: bool,
            existing_build_dir: Optional[str],
            parallelism: Optional[int],
            target_arch: str) -> None:
        self.install_parent_dir = install_parent_dir
        self.version = version
        self.gcc_major_version = get_major_version(version)
        assert self.gcc_major_version >= 12
        self.user_specified_suffix = user_specified_suffix
        self.skip_auto_suffix = skip_auto_suffix
        self.git_sha1_prefix = None

        self.clean_build = clean_build
        self.build_start_timestamp_str = get_current_timestamp_str()

        self.unix_timestamp_for_suffix = None

        self.existing_build_dir = existing_build_dir
        self.tag_override = None
        if self.existing_build_dir:
            build_dir_basename = os.path.basename(self.existing_build_dir)
            invalid_msg_prefix = \
                f"Invalid existing build directory basename: '{build_dir_basename}', "
            if not build_dir_basename.endswith(BUILD_DIR_SUFFIX_WITH_SEPARATOR):
                raise ValueError(
                    invalid_msg_prefix +
                    f"does not end with '{BUILD_DIR_SUFFIX_WITH_SEPARATOR}'.")
            if not build_dir_basename.startswith(YB_GCC_ARCHIVE_NAME_PREFIX):
                raise ValueError(
                    invalid_msg_prefix +
                    f"does not start with '{YB_GCC_ARCHIVE_NAME_PREFIX}'.")
            self.tag_override = build_dir_basename[
                len(YB_GCC_ARCHIVE_NAME_PREFIX):-len(BUILD_DIR_SUFFIX_WITH_SEPARATOR)]
        else:
            self.unix_timestamp_for_suffix = str(int(time.time()))

        self.parallelism = parallelism
        self.target_arch = target_arch

    def get_gcc_build_parent_dir(self) -> str:
        return os.path.join(
            self.install_parent_dir,
            self.get_install_dir_basename() + BUILD_DIR_SUFFIX_WITH_SEPARATOR)

    def get_tag(self) -> str:
        if self.tag_override:
            return self.tag_override

        top_dir_suffix = ''
        if not self.skip_auto_suffix:
            sys_conf = sys_detection.local_sys_conf()
            components = [
                component for component in [
                    self.unix_timestamp_for_suffix,
                    self.git_sha1_prefix or GIT_SHA1_PLACEHOLDER_STR,
                    self.user_specified_suffix,
                    sys_conf.short_os_name_and_version(),
                    sys_conf.architecture
                ] if component
            ]
            top_dir_suffix = NAME_COMPONENT_SEPARATOR + NAME_COMPONENT_SEPARATOR.join(
                    components)

        return 'v%s%s' % (self.version, top_dir_suffix)

    def get_install_dir_basename(self) -> str:
        return YB_GCC_ARCHIVE_NAME_PREFIX + self.get_tag()

    def get_final_install_dir(self) -> str:
        return os.path.join(
            self.install_parent_dir,
            self.get_install_dir_basename())

    def get_gcc_build_info_dir(self) -> str:
        return os.path.join(self.get_final_install_dir(), 'etc', 'yb-gcc-build-info')

    def get_gcc_clone_dir(self) -> str:
        return os.path.join(self.get_gcc_build_parent_dir(), GCC_CLONE_REL_PATH)

    def set_git_sha1(self, git_sha1: str) -> None:
        old_build_parent_dir = self.get_gcc_build_parent_dir()

        self.git_sha1_prefix = git_sha1[:GIT_SHA1_PREFIX_LENGTH]
        logging.info("Git SHA1: %s", git_sha1)
        logging.info("Using git SHA1 prefix: %s", self.git_sha1_prefix)
        logging.info("Renaming %s -> %s", old_build_parent_dir, self.get_gcc_build_parent_dir())
        os.rename(old_build_parent_dir, self.get_gcc_build_parent_dir())
