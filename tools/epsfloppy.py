#!/usr/bin/env python3
"""Write and read real Ensoniq EPS floppies from a computer.

  epsfloppy.py devices                       Show the floppy hardware found
  epsfloppy.py write IMAGE [--fdc DEV]       Write an .ede/.img to a floppy
  epsfloppy.py read  IMAGE [--fdc DEV]       Read a floppy to an .ede/.img

An EPS disk is 3.5" DD, 80 cyl x 2 heads x 10 sectors of 512 bytes, and its
sectors are numbered 0-9 on every track. PC disks number sectors from 1.
That is why ordinary USB floppy drives can't do it: their firmware only
formats and addresses standard PC layouts (720K / 1.44M, sectors from 1),
and the computer can't change that. Two kinds of hardware can:

* Greaseweazle (default backend): a small USB adapter that drives a normal
  PC 3.5" floppy drive at the flux level. Works on Linux, macOS and Windows.
  Needs the `gw` tool (pip install greaseweazle); this script calls
  `gw write/read --format=ensoniq.800`.
* --fdc /dev/fd0: a floppy drive on a PC motherboard's floppy controller,
  Linux only, run as root. The kernel driver is switched to a zero-based
  10-sector layout, each track is formatted, then the image is written and
  read back to verify.

Use a DD disk (or tape over the HD hole) - the EPS drive is double density.
"""
import argparse
import ctypes
import glob
import os
import shutil
import stat
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import epstool  # noqa: E402

try:
    import fcntl     # --fdc only; not available on Windows
except ImportError:
    fcntl = None

CYLS, HEADS, SECTS = 80, 2, 10
TRACK_BYTES = SECTS * epstool.BLOCK
GW_FORMAT = "ensoniq.800"
FLOPPY_MAJOR = 2


# ---------------------------------------------------------- Greaseweazle

def gw_exe(path):
    exe = path or shutil.which("gw")
    if not exe:
        sys.exit("Greaseweazle tool `gw` not found. Install it with "
                 "`pip install greaseweazle`, or use --fdc on Linux.")
    return exe


def gw_run(args, verb, path):
    cmd = [gw_exe(args.gw), verb, f"--format={GW_FORMAT}", f"--drive={args.drive}"]
    if args.device:
        cmd.append(f"--device={args.device}")
    if getattr(args, "no_verify", False):
        cmd.append("--no-verify")
    cmd.append(path)
    print("+ " + " ".join(cmd))
    if subprocess.run(cmd).returncode:
        sys.exit(f"gw {verb} failed")


# ------------------------------------------------------- Linux floppy (FDC)

class FloppyStruct(ctypes.Structure):          # <linux/fd.h> struct floppy_struct
    _fields_ = [("size", ctypes.c_uint), ("sect", ctypes.c_uint),
                ("head", ctypes.c_uint), ("track", ctypes.c_uint),
                ("stretch", ctypes.c_uint), ("gap", ctypes.c_ubyte),
                ("rate", ctypes.c_ubyte), ("spec1", ctypes.c_ubyte),
                ("fmt_gap", ctypes.c_ubyte), ("name", ctypes.c_char_p)]


class FormatDescr(ctypes.Structure):           # struct format_descr
    _fields_ = [("device", ctypes.c_uint), ("head", ctypes.c_uint),
                ("track", ctypes.c_uint)]


def _ioc(direction, nr, size):
    return (direction << 30) | (size << 16) | (2 << 8) | nr   # type 2 = floppy


FDSETPRM = _ioc(1, 0x42, ctypes.sizeof(FloppyStruct))
FDFMTBEG = _ioc(0, 0x47, 0)
FDFMTTRK = _ioc(1, 0x48, ctypes.sizeof(FormatDescr))
FDFMTEND = _ioc(0, 0x49, 0)
FDFLUSH = _ioc(0, 0x4B, 0)
FD_ZEROBASED = 4

# The kernel's own "D800" (u800) entry, with sector numbering moved to 0.
EPS_GEOMETRY = FloppyStruct(size=CYLS * HEADS * SECTS, sect=SECTS, head=HEADS,
                            track=CYLS, stretch=FD_ZEROBASED, gap=0x25,
                            rate=0x02, spec1=0xDF, fmt_gap=0x2E)


def usb_floppies():
    """Block devices behind a USB floppy (UFI) interface."""
    out = []
    for dev in glob.glob("/sys/block/sd*"):
        p = os.path.realpath(os.path.join(dev, "device"))
        while p != "/":
            sub = os.path.join(p, "bInterfaceSubClass")
            if os.path.exists(sub):
                if open(sub).read().strip() == "04":   # mass storage UFI
                    out.append("/dev/" + os.path.basename(dev))
                break
            p = os.path.dirname(p)
    return out


def open_fdc(dev, mode):
    try:
        st = os.stat(dev)
    except FileNotFoundError:
        sys.exit(f"{dev} not found (is the floppy module loaded? modprobe floppy)")
    if fcntl is None:
        sys.exit("--fdc only works on Linux; use a Greaseweazle")
    if not stat.S_ISBLK(st.st_mode) or os.major(st.st_rdev) != FLOPPY_MAJOR:
        hint = (" It is a USB floppy drive, which can only make PC-format disks."
                if dev in usb_floppies() else "")
        sys.exit(f"{dev} is not a motherboard floppy drive (/dev/fd0, /dev/fd1).{hint}"
                 " Use a Greaseweazle instead (drop --fdc).")
    if os.geteuid() != 0:
        sys.exit("--fdc needs root to set the disk geometry (run with sudo)")
    fd = os.open(dev, mode | os.O_NDELAY)
    fcntl.ioctl(fd, FDSETPRM, EPS_GEOMETRY)
    return fd


def fdc_write(img, dev, verify):
    fd = open_fdc(dev, os.O_RDWR)
    try:
        fcntl.ioctl(fd, FDFMTBEG)
        for cyl in range(CYLS):
            for head in range(HEADS):
                fcntl.ioctl(fd, FDFMTTRK, FormatDescr(0, head, cyl))
            print(f"\rformat cyl {cyl:2d}", end="", flush=True)
        fcntl.ioctl(fd, FDFMTEND)
        print()
        # Linear block order on /dev/fdN is cyl, head, sector - same as the .img.
        os.lseek(fd, 0, os.SEEK_SET)
        for t in range(CYLS * HEADS):
            os.write(fd, img[t * TRACK_BYTES:(t + 1) * TRACK_BYTES])
            print(f"\rwrite cyl {t // 2:2d}", end="", flush=True)
        os.fsync(fd)
        print()
    finally:
        os.close(fd)
    if verify:
        back = fdc_read(dev)
        bad = [b for b in range(epstool.NBLOCKS) if epstool.blk(back, b) != epstool.blk(img, b)]
        if bad:
            sys.exit(f"verify FAILED on {len(bad)} blocks (first: {bad[:8]}) - try another disk")
        print("verify OK")


def fdc_read(dev):
    fd = open_fdc(dev, os.O_RDONLY)
    try:
        fcntl.ioctl(fd, FDFLUSH)     # drop cached blocks so we read the disk
        os.lseek(fd, 0, os.SEEK_SET)
        data = bytearray()
        for t in range(CYLS * HEADS):
            chunk = os.read(fd, TRACK_BYTES)
            if len(chunk) != TRACK_BYTES:
                sys.exit(f"short read at cyl {t // 2} head {t % 2}")
            data += chunk
            print(f"\rread cyl {t // 2:2d}", end="", flush=True)
        print()
        return data
    finally:
        os.close(fd)


# ------------------------------------------------------------------- CLI

def cmd_devices(args):
    exe = args.gw or shutil.which("gw")
    print(f"Greaseweazle tool: {exe or 'not installed (pip install greaseweazle)'}")
    if exe:
        subprocess.run([exe, "info"])
    if sys.platform.startswith("linux"):
        fds = sorted(glob.glob("/dev/fd[0-9]"))
        print("Motherboard floppy (--fdc):", ", ".join(fds) or "none")
        usb = usb_floppies()
        if usb:
            print("USB floppy drives:", ", ".join(usb),
                  "- can't write EPS disks (PC formats only)")


def cmd_write(args):
    img = epstool.load_image(args.image)
    if args.fdc:
        fdc_write(img, args.fdc, not args.no_verify)
        return
    with tempfile.TemporaryDirectory() as t:
        path = os.path.join(t, "eps.img")
        open(path, "wb").write(img)
        gw_run(args, "write", path)


def cmd_read(args):
    if args.fdc:
        img = fdc_read(args.fdc)
    else:
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "eps.img")
            gw_run(args, "read", path)
            img = open(path, "rb").read()
    if len(img) != epstool.NBLOCKS * epstool.BLOCK:
        sys.exit(f"read {len(img)} bytes, expected {epstool.NBLOCKS * epstool.BLOCK}")
    epstool.save_image(bytearray(img), args.image)
    print(f"saved {args.image}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    for name, fn, img_help in (("devices", cmd_devices, None),
                               ("write", cmd_write, "disk image to write (.ede or .img)"),
                               ("read", cmd_read, "image to save (.ede or .img)")):
        a = sp.add_parser(name)
        a.set_defaults(fn=fn)
        a.add_argument("--gw", metavar="PATH", help="path to the gw tool")
        if img_help:
            a.add_argument("image", help=img_help)
            a.add_argument("--fdc", metavar="DEV",
                           help="use a motherboard floppy drive (Linux, e.g. /dev/fd0)")
            a.add_argument("--drive", default="A",
                           help="Greaseweazle drive: A, B, 0, 1, 2 (default A)")
            a.add_argument("--device", help="Greaseweazle serial port, if not found")
        if name == "write":
            a.add_argument("--no-verify", action="store_true",
                           help="skip the read-back check")
    args = p.parse_args()
    try:
        args.fn(args)
    except OSError as e:
        sys.exit(f"error: {e} (no disk, write-protected, or bad disk?)")


if __name__ == "__main__":
    main()
