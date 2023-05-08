import pefile


def _patch_dll(
    lib_to_mangle: str, lib_mangled_name: str, lib_to_patch: str
) -> int:
    """Patch lib_to_patch replacing the name of a dependency."""
    dlllib = pefile.PE(lib_to_patch)
    for entry in dlllib.DIRECTORY_ENTRY_IMPORT:
        if entry.dll.decode("utf-8") == lib_to_mangle:
            if not dlllib.set_bytes_at_rva(
                entry.struct.Name, 
                lib_mangled_name.encode('ascii') + '\0'
            ):
                raise RuntimeError(
                    f"Unable to apply mangling to {lib_to_patch}, "
                    f"{lib_to_mangle}->{lib_mangled_name}"
                )
    dlllib.merge_modified_section_data()
    dlllib.write(lib_to_patch)
