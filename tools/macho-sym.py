#!/usr/bin/env python3
"""Print the Mach-O symbol nearest below an address (kernel debugging helper).

  python macho-sym.py KERNEL 0xfffffff0078125b0 [...]
"""
import struct
import sys

LC_SYMTAB = 0x2
N_STAB = 0xe0
N_TYPE = 0x0e
N_SECT = 0x0e


def symbols(path):
    buf = open(path, 'rb').read()
    magic, _, _, _, ncmds, _, _, _ = struct.unpack_from('<8I', buf, 0)
    assert magic == 0xfeedfacf, 'not a 64-bit Mach-O'
    off = 32
    symtab = None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', buf, off)
        if cmd == LC_SYMTAB:
            symtab = struct.unpack_from('<4I', buf, off + 8)
        off += size
    if not symtab:
        return []
    symoff, nsyms, stroff, strsize = symtab
    out = []
    for i in range(nsyms):
        strx, ntype, sect, desc, value = struct.unpack_from('<IBBHQ', buf, symoff + i * 16)
        if ntype & N_STAB or (ntype & N_TYPE) != N_SECT or not value:
            continue
        end = buf.index(b'\0', stroff + strx)
        name = buf[stroff + strx:end].decode(errors='replace')
        out.append((value, name))
    out.sort()
    return out


def main():
    path = sys.argv[1]
    syms = symbols(path)
    print(f'{len(syms)} symbols in {path}')
    for text in sys.argv[2:]:
        addr = int(text, 0)
        best = None
        for value, name in syms:
            if value <= addr:
                best = (value, name)
            else:
                break
        if best:
            print(f'{text}: {best[1]}+{addr - best[0]:#x} (symbol {best[0]:#x})')
        else:
            print(f'{text}: no symbol below')


if __name__ == '__main__':
    main()
