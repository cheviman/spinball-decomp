"""
Name:        spinball_rom.py
Description: Sonic the Hedgehog Spinball's cartridge (Mega Drive / Genesis, USA) and the program as the 68000
             sees it
Version:     0.1.0
Created:     13-11-2026
Modified:    13-11-2026
Author:      Sebastian Toyos

The cartridge is one 1 MiB file, known by its CRC32 and SHA-1, not by its name: a ROM file, a .zip holding it,
or a folder holding either. It is the program and its data at 000000-0FFFFF, big endian, as the 68000 sees it.
"""
import hashlib
import zipfile
import zlib
from pathlib import Path

SET_NAME = "Sonic the Hedgehog Spinball (USA)"
CARTRIDGE = ("677206cb", "24bf6342b98c09775089c9f39cfb2f6fbe7806f7", 0x100000)    # crc32, sha1, size

PROGRAM_AREAS = [(0x000000, 0x100000)]
PROGRAM_SIZE = 0x100000


def _candidates(source):
    """(name, bytes) of every file 'source' holds or is: a ROM file, a .zip's entries, a folder's files and
    .zips"""
    source = Path(source)
    paths = sorted(path for path in source.iterdir() if path.is_file()) if source.is_dir() else [source]
    for path in paths:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for entry in archive.infolist():
                    if not entry.is_dir() and entry.file_size == CARTRIDGE[2]:
                        yield f"{path.name}:{entry.filename}", archive.read(entry)
        elif path.stat().st_size == CARTRIDGE[2]:
            yield path.name, path.read_bytes()


def identify_set(source):
    """({"cartridge": bytes} or {}, [report lines])"""
    report = []
    for name, data in _candidates(source):
        crc = format(zlib.crc32(data) & 0xFFFFFFFF, "08x")
        if crc == CARTRIDGE[0] and hashlib.sha1(data).hexdigest() == CARTRIDGE[1]:
            report.append(f"OK      {name} = {SET_NAME}")
            return {"cartridge": data}, report
        report.append(f"--      {name} is not the cartridge (crc {crc})")
    report.append(f"MISSING {SET_NAME}: 1 MiB, CRC32 {CARTRIDGE[0].upper()}")
    return {}, report


def load_set(source):
    """Like identify_set, but stops when the cartridge is not there."""
    found, _ = identify_set(source)
    if not found:
        raise SystemExit(f"{SET_NAME} is not in {source}: 1 MiB, CRC32 {CARTRIDGE[0].upper()}")
    return found


def build_program(rom):
    """The cartridge as the 68000 sees it at 000000-0FFFFF."""
    return bytes(rom["cartridge"])


def canonical_address(address):
    """A 68000 address's offset in the program image, or None if it is not the cartridge (24 address lines;
    the cartridge's space at 000000-3FFFFF holds 1 MiB, which this program does not mirror)."""
    address &= 0xFFFFFF
    return address if address < PROGRAM_SIZE else None


class ProgramMemory:
    """The 68000's view of the cartridge for the disassembler: big endian, anything outside it reads 0xFF."""

    def __init__(self, image):
        self.image = image

    def r8(self, address):
        offset = canonical_address(address)
        return self.image[offset] if offset is not None else 0xFF

    def r16(self, address):
        return (self.r8(address) << 8) | self.r8(address + 1)

    def r32(self, address):
        return (self.r16(address) << 16) | self.r16(address + 2)
