import argparse
import os
import logging
import platform

from typing import Tuple, Union

from sys_detection import is_linux

from build_gcc.constants import (
    DEFAULT_INSTALL_PARENT_DIR,
    DEFAULT_GITHUB_ORG,
    GCC_VERSION_MAP,
)
from build_gcc.helpers import get_major_version
from build_gcc.gcc_build_conf import GCCBuildConf


def convert_bool_arg(value: Union[str, bool]) -> bool:
    if isinstance(value, bool):
        return value
    normalized_value = value.lower()
    if normalized_value in ('yes', 'true', 't', 'y', '1'):
        return True
    if normalized_value in ('no', 'false', 'f', 'n', '0'):
        return False
    raise argparse.ArgumentTypeError(f"Boolean value expected. Got {value}.")


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Build GCC')
    parser.add_argument(
        '--install_parent_dir',
        help='Parent directory of the final installation directory. Default: %s' %
             DEFAULT_INSTALL_PARENT_DIR,
        default=DEFAULT_INSTALL_PARENT_DIR)
    parser.add_argument(
        '--local_build',
        help='Run the build locally, even if BUILD_GCC_REMOTE_... variables are set.',
        action='store_true')
    parser.add_argument(
        '--remote_server', help='Server to build on',
        default=os.getenv('BUILD_GCC_REMOTE_SERVER'))
    parser.add_argument(
        '--remote_build_scripts_path',
        help='Remote directory for the build-gcc project repo',
        default=os.getenv('BUILD_GCC_REMOTE_BUILD_SCRIPTS_PATH'))
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean the build directory before the build')
    parser.add_argument(
        '--top_dir_suffix',
        help='Suffix to append to the top-level directory that we will use for the build. ')
    parser.add_argument(
        '--gcc_version',
        help='GCC version to build, e.g. 12, 13, 12.5.0, etc',
        default='15')
    parser.add_argument(
        '--skip_auto_suffix',
        help='Do not add automatic suffixes based on Git commit SHA1 and current time to the '
             'build directory and the archive name. This is useful for incremental builds when '
             'debugging build-gcc scripts.',
        action='store_true')
    parser.add_argument(
        '--upload_earlier_build',
        help='Upload earlier build specified by this path. This is useful for debugging '
             'release upload to GitHub.')
    parser.add_argument(
        '--reuse_tarball',
        help='Reuse existing tarball (for use with --upload_earlier_build).',
        action='store_true')
    parser.add_argument(
        '--existing_build_dir',
        help='Continue build in an existing directory, e.g. '
             '/opt/yb-build/gcc/yb-gcc-v12.5.0-1618898532-d28af7c6-build. '
             'This helps when developing these scripts to avoid rebuilding from scratch.')
    parser.add_argument(
        '--parallelism', '-j',
        type=int,
        help='Set the parallelism level for Ninja builds'
    )
    parser.add_argument(
        '--github_org',
        help='GitHub organization to use in the clone URL. Default: ' + DEFAULT_GITHUB_ORG,
        default=DEFAULT_GITHUB_ORG
    )
    parser.add_argument(
        '--skip_build',
        help='Skip building. Useful for debugging, or when combined with '
             '--existing_build_dir, when you want to upload an existing build.',
        action='store_true')
    parser.add_argument(
        '--skip_upload',
        help='Skip package upload',
        action='store_true')

    parser.add_argument(
        '--target_arch',
        help='Target architecture to build for.',
        choices=['x86_64', 'aarch64', 'arm64'])

    return parser


def parse_args() -> Tuple[argparse.Namespace, GCCBuildConf]:
    parser = create_arg_parser()
    args = parser.parse_args()

    if args.existing_build_dir:
        logging.info("Assuming --skip_auto_suffix because --existing_build_dir is set")
        args.skip_auto_suffix = True

    adjusted_gcc_version = GCC_VERSION_MAP.get(
        args.gcc_version, args.gcc_version)
    if args.gcc_version != adjusted_gcc_version:
        logging.info("Automatically substituting GCC version %s for %s",
                     adjusted_gcc_version, args.gcc_version)
    args.gcc_version = adjusted_gcc_version

    gcc_major_version = get_major_version(args.gcc_version)

    logging.info("GCC major version: %d", gcc_major_version)

    target_arch_arg = args.target_arch
    target_arch_from_env = os.environ.get('YB_TARGET_ARCH')
    current_arch = platform.machine()

    arch_agreement = [
        arch for arch in [target_arch_arg, target_arch_from_env, current_arch]
        if arch is not None
    ]
    if len(set(arch_agreement)) != 1:
        raise ValueError(
            "Target architecture is ambiguous: %s. "
            "--target_arch arg is %s, YB_TARGET_ARCH env var is %s, "
            "platform.machine() is %s" % (
                arch_agreement,
                target_arch_arg,
                target_arch_from_env,
                current_arch))

    build_conf = GCCBuildConf(
        install_parent_dir=args.install_parent_dir,
        version=args.gcc_version,
        user_specified_suffix=args.top_dir_suffix,
        skip_auto_suffix=args.skip_auto_suffix,
        clean_build=args.clean,
        existing_build_dir=args.existing_build_dir,
        parallelism=args.parallelism,
        target_arch=current_arch,
    )

    return args, build_conf
