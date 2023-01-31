import sys
import os
import tempfile
import subprocess
import pathlib


def consolidate(wheels):
    wheels = [os.path.abspath(w) for w in wheels]
    with tempfile.TemporaryDirectory() as tmpcd:
        curdir = os.getcwd()
        print(f"Working inside {tmpcd}")
        os.chdir(tmpcd)

        unpackwheels(wheels)
        wheeldirs = os.listdir(tmpcd)
        mangling_map = buildlibmap(wheeldirs)
        print(f"Applying consistent mangling: {mangling_map}")
        patch_wheeldirs(wheeldirs, mangling_map)
        packwheels(wheeldirs, curdir)


def patch_wheeldirs(wheeldirs, mangling_map):
    for wheeldir in wheeldirs:
        for lib_to_patch in pathlib.Path(wheeldir).rglob('*.so'):
            print(f"Patching {lib_to_patch}")
            for lib_to_mangle, lib_mangled_name in mangling_map.items():
                print(f"  {lib_to_mangle} -> {lib_mangled_name}")
                if subprocess.call(['patchelf', '--replace-needed', lib_to_mangle, lib_mangled_name, lib_to_patch]):
                    raise RuntimeError(f"Unable to apply mangling to {lib_to_patch}, {lib_to_mangle}->{lib_mangled_name}")


def buildlibmap(wheeldirs):
    all_shared_objects = {}
    for wheeldir in wheeldirs:
        for lib in pathlib.Path(wheeldir).rglob('*.libs/*.so'):
            lib = os.path.basename(lib)
            libname, extension = os.path.splitext(lib)
            demangled_libname = libname.rsplit('-', 1)[0]
            demangled_lib = f'{demangled_libname}{extension}'
            all_shared_objects[demangled_lib] = lib
    return all_shared_objects


def unpackwheels(wheels):
    for wheel in wheels:
        if subprocess.call(["wheel", "unpack", wheel]):
            raise RuntimeError(f"Unable to unpack {wheel}")


def packwheels(wheeldirs, destdir):
    for wheeldir in wheeldirs:
        if subprocess.call(["wheel", "pack", wheeldir, "--dest-dir", destdir]):
            raise RuntimeError(f"Unable to pack {wheel} into {destdir}")


if __name__ == '__main__':
    consolidate(sys.argv[1:])