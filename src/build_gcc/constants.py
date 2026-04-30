from build_gcc.helpers import multiline_str_to_list
import os


# Length of Git SHA1 prefix to be used in directory name.
GIT_SHA1_PREFIX_LENGTH = 8

DEVTOOLSET_ENV_VARS = set(multiline_str_to_list("""
    INFOPATH
    LD_LIBRARY_PATH
    MANPATH
    PATH
    PCP_DIR
    PERL5LIB
    PKG_CONFIG_PATH
    PYTHONPATH
"""))

YB_GCC_ARCHIVE_NAME_PREFIX = 'yb-gcc-'

BUILD_DIR_SUFFIX = 'build'
NAME_COMPONENT_SEPARATOR = '-'
BUILD_DIR_SUFFIX_WITH_SEPARATOR = NAME_COMPONENT_SEPARATOR + BUILD_DIR_SUFFIX

DEFAULT_INSTALL_PARENT_DIR = '/opt/yb-build/gcc'

# Relative path to the directory where we clone the GCC source code.
GCC_CLONE_REL_PATH = os.path.join('src', 'gcc')

# Relative path to the directory where we clone the binutils source code.
BINUTILS_CLONE_REL_PATH = os.path.join('src', 'binutils')

# Relative path to the directory where we combine GCC and binutils.
COMBINED_TREE_REL_PATH = os.path.join('src', 'combined')

GIT_SHA1_PLACEHOLDER_STR = 'GIT_SHA1_PLACEHOLDER'
GIT_SHA1_PLACEHOLDER_STR_WITH_SEPARATORS = (
    NAME_COMPONENT_SEPARATOR + GIT_SHA1_PLACEHOLDER_STR + NAME_COMPONENT_SEPARATOR)

GCC_VERSION_MAP = {
    '12': '12.2.0',
    '13': '13.2.0',
    '14': '14.3.0',
    '15': '15.2.0',
}

DEFAULT_GCC_GIT = 'git://gcc.gnu.org/git/gcc.git'

BINUTILS_VERSION_MAP = {
    '12': '2.38',
    '13': '2.40',
    '14': '2.43',
    '15': '2.45',
}

DEFAULT_BINUTILS_GIT = 'git://sourceware.org/git/binutils-gdb.git'

BUILD_GCC_SCRIPTS_ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
