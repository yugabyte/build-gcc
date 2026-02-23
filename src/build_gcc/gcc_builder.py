import os
import logging
import shlex
import subprocess
import git
import atexit
import time
import platform

from typing import Any, List, Optional

from sys_detection import is_linux, is_macos

from build_gcc.constants import (
    GCC_CLONE_REL_PATH,
    GIT_SHA1_PLACEHOLDER_STR_WITH_SEPARATORS,
    YB_GCC_ARCHIVE_NAME_PREFIX,
    BUILD_GCC_SCRIPTS_ROOT_PATH,
)
from build_gcc.helpers import (
    mkdir_p,
    remove_version_suffix,
    rm_rf,
    run_cmd,
    ChangeDir,
)
from build_gcc.gcc_build_conf import GCCBuildConf
from build_gcc.git_helpers import git_clone_tag, get_current_git_sha1, save_git_log_to_file
from build_gcc import remote_build
from build_gcc.devtoolset import activate_devtoolset
from build_gcc.cmd_line_args import parse_args
from build_gcc.architecture import validate_build_output_arch, get_arch_switch_cmd_prefix
from build_gcc.devtoolset import find_latest_gcc


class GCCBuilder:
    args: Any
    gcc_parent_dir: str
    build_conf: GCCBuildConf

    def parse_args(self) -> None:
        self.args, self.build_conf = parse_args()

    def clone_gcc_source_code(self) -> None:
        gcc_src_path = self.build_conf.get_gcc_clone_dir()
        logging.info(f"Cloning GCC code to {gcc_src_path}")

        mkdir_p('/opt/yb-build/gcc')
        find_cmd = [
            'find', '/opt/yb-build/gcc', '-mindepth', '3', '-maxdepth', '3',
            '-wholename', os.path.join('*', GCC_CLONE_REL_PATH)
        ]
        logging.info("Searching for existing GCC source directories using command: %s",
                     ' '.join([shlex.quote(item) for item in find_cmd]))
        existing_src_dirs = subprocess.check_output(find_cmd).decode('utf-8').split('\n')

        tag_we_want = 'releases/gcc-%s' % self.build_conf.version

        existing_dir_to_use: Optional[str] = None
        gcc_repo_url = f'https://github.com/{self.args.github_org}/gcc.git'
        for existing_src_dir in existing_src_dirs:
            existing_src_dir = existing_src_dir.strip()
            if not existing_src_dir:
                continue
            if not os.path.exists(existing_src_dir):
                logging.warning("Directory %s does not exist", existing_src_dir)
                continue

            repo = git.Repo(existing_src_dir)
            # From https://stackoverflow.com/questions/34932306/get-tags-of-a-commit
            # Also relevant:
            # https://stackoverflow.com/questions/32523121/gitpython-get-current-tag-detached-head
            for tag in repo.tags:
                tag_commit = repo.commit(tag)
                if tag_commit.hexsha == repo.head.commit.hexsha:
                    logging.info(
                        f"Found tag {tag.name} in {existing_src_dir} "
                        f"matching the head SHA1 {repo.head.commit.hexsha}")
                    if tag.name == tag_we_want:
                        existing_dir_to_use = existing_src_dir
                        logging.info(
                            "This tag matches the name we want: %s, will clone from directory %s",
                            tag_we_want, existing_dir_to_use)
                        break
            if existing_dir_to_use:
                break
        if not existing_dir_to_use:
            logging.info("Did not find an existing checkout of tag %s, will clone %s",
                         tag_we_want, gcc_repo_url)

        if GIT_SHA1_PLACEHOLDER_STR_WITH_SEPARATORS in os.path.basename(
                os.path.dirname(os.path.dirname(gcc_src_path))):
            def remove_dir_with_placeholder_in_name() -> None:
                if os.path.exists(gcc_src_path):
                    logging.info("Removing directory %s", gcc_src_path)
                    subprocess.call(['rm', '-rf', gcc_src_path])
                else:
                    logging.warning("Directory %s does not exist, nothing to remove",
                                    gcc_src_path)
            atexit.register(remove_dir_with_placeholder_in_name)

        git_clone_tag(
            gcc_repo_url if existing_dir_to_use is None else existing_dir_to_use,
            tag_we_want,
            gcc_src_path)

    def run(self) -> None:
        if os.getenv('BUILD_GCC_REMOTELY') == '1' and not self.args.local_build:
            remote_build.build_remotely(
                remote_server=self.args.remote_server,
                remote_build_scripts_path=self.args.remote_build_scripts_path,
                # TODO: make this an argument?
                remote_mkdir=True
            )
            return

        activate_devtoolset()

        if (self.args.existing_build_dir is not None and
                self.build_conf.get_gcc_build_parent_dir() != self.args.existing_build_dir):
            logging.warning(
                f"User-specified build directory : {self.args.existing_build_dir}")
            logging.warning(
                f"Computed build directory       : {self.build_conf.get_gcc_build_parent_dir()}")
            raise ValueError("Build directory mismatch, see the details above.")

        if not self.args.upload_earlier_build:
            if self.args.existing_build_dir:
                logging.info("Not cloning the code, assuming it has already been done.")
            else:
                self.clone_gcc_source_code()
                mkdir_p(self.build_conf.get_gcc_build_info_dir())

            if not self.args.skip_auto_suffix:
                git_sha1 = get_current_git_sha1(self.build_conf.get_gcc_clone_dir())
                self.build_conf.set_git_sha1(git_sha1)
                logging.info(
                    "Final GCC code directory: %s",
                    self.build_conf.get_gcc_clone_dir())

            logging.info(
                "GCC will be built and installed to: %s",
                self.build_conf.get_final_install_dir())

            save_git_log_to_file(
                self.build_conf.get_gcc_clone_dir(),
                os.path.join(
                    self.build_conf.get_gcc_build_info_dir(), 'gcc_git_log.txt'))

            if self.args.skip_build:
                logging.info("Skipping build, --skip_build specified")
            else:
                build_start_time_sec = time.time()
                logging.info("Building GCC")
                self.do_build()
                build_elapsed_time_sec = time.time() - build_start_time_sec
                logging.info("Built GCC %.1f seconds", build_elapsed_time_sec)

        final_install_dir = (
            self.args.upload_earlier_build or self.build_conf.get_final_install_dir())

        final_install_dir_basename = os.path.basename(final_install_dir)
        final_install_parent_dir = os.path.dirname(final_install_dir)
        archive_name = final_install_dir_basename + '.tar.gz'
        archive_path = os.path.join(final_install_parent_dir, archive_name)

        if not self.args.reuse_tarball or not os.path.exists(archive_path):
            if os.path.exists(archive_path):
                logging.info("Removing existing archive %s", archive_path)
                try:
                    os.remove(archive_path)
                except OSError as ex:
                    logging.exception("Failed to remove %s, ignoring the error", archive_path)

            run_cmd(
                ['tar', 'czf', archive_name, final_install_dir_basename],
                cwd=final_install_parent_dir,
            )

        if is_macos():
            sha_sum_cmd_line = ['shasum', '-a', '256']
        else:
            sha_sum_cmd_line = ['sha256sum']
        sha_sum_cmd_line.append(archive_path)
        sha256sum_output = subprocess.check_output(sha_sum_cmd_line).decode('utf-8')
        sha256sum_file_path = archive_path + '.sha256'
        with open(sha256sum_file_path, 'w') as sha256sum_file:
            sha256sum_file.write(sha256sum_output)

        assert final_install_dir_basename.startswith(YB_GCC_ARCHIVE_NAME_PREFIX)
        tag = final_install_dir_basename[len(YB_GCC_ARCHIVE_NAME_PREFIX):]

        if self.args.skip_upload:
            logging.info("Skipping upload")
            return

        github_token_path = os.path.expanduser('~/.github-token')
        if os.path.exists(github_token_path) and not os.getenv('GITHUB_TOKEN'):
            logging.info("Reading GitHub token from %s", github_token_path)
            with open(github_token_path) as github_token_file:
                os.environ['GITHUB_TOKEN'] = github_token_file.read().strip()

        run_cmd([
            'hub',
            'release',
            'create', tag,
            '-m', 'Release %s' % tag,
            '-a', archive_path,
            '-a', sha256sum_file_path,
        ], cwd=BUILD_GCC_SCRIPTS_ROOT_PATH)

    def do_build(self) -> None:
        parent_dir_for_gcc_version = self.build_conf.get_gcc_build_parent_dir()
        build_dir = os.path.join(parent_dir_for_gcc_version, 'build')
        install_prefix = self.build_conf.get_final_install_dir()

        if os.path.exists(build_dir) and self.build_conf.clean_build:
            logging.info("Deleting directory: %s", build_dir)
            rm_rf(build_dir)

        c_compiler, cxx_compiler = find_latest_gcc()
        parallelism = self.build_conf.parallelism
        if parallelism is None:
            parallelism = os.cpu_count()

        with ChangeDir(self.build_conf.get_gcc_clone_dir()):
            logging.info("Running download_prerequisites")
            run_cmd(get_arch_switch_cmd_prefix(self.build_conf.target_arch) + [
                os.path.join('contrib', 'download_prerequisites')
            ])

        mkdir_p(build_dir)
        with ChangeDir(build_dir):
            configure_args = [
                f'--prefix={install_prefix}',
                '--disable-multilib',
                '--disable-nls',
                '--enable-languages=c,c++,lto',
                '--enable-lto',
                '--with-build-config=bootstrap-O3 bootstrap-lto',
                f'CC={c_compiler}',
                f'CXX={cxx_compiler}',
            ]

            logging.info("Running configure")
            run_cmd(get_arch_switch_cmd_prefix(self.build_conf.target_arch) + [
                os.path.join(self.build_conf.get_gcc_clone_dir(), 'configure')
            ] + configure_args)

            logging.info("Building GCC")
            run_cmd(get_arch_switch_cmd_prefix(self.build_conf.target_arch) + [
                'make', '-j', str(parallelism), 'profiledbootstrap'
            ])

            logging.info("Installing GCC")
            run_cmd(get_arch_switch_cmd_prefix(self.build_conf.target_arch) + [
                'make', 'install'
            ])

            validate_build_output_arch(self.build_conf.target_arch, install_prefix)
