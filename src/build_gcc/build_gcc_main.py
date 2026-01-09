#!/usr/bin/env python3

import logging

from build_gcc.gcc_builder import GCCBuilder


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(filename)s:%(lineno)d] %(asctime)s %(levelname)s: %(message)s")
    builder = GCCBuilder()
    builder.parse_args()
    builder.run()


if __name__ == '__main__':
    main()
