from exporter.fragment import FragmentedJsonList

import os
import shutil
import sys
import tempfile

src_dir = sys.argv[1]

with tempfile.TemporaryDirectory() as tempdir:
    src = FragmentedJsonList(src_dir)
    dst = FragmentedJsonList(tempdir)

    dst.extend(src[::-1])

    src.close()

    shutil.rmtree(src_dir)

    src = FragmentedJsonList(src_dir)
    src.extend(dst[::])
    src.close()
    dst.close()

print("OK")