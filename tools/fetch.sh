#!/bin/sh
# Download the stock OS images and reference documents into build/.
# Nothing fetched here is committed (see .gitignore).
#
#   tools/fetch.sh          OS 2.49 + older OS versions + schematics/manuals
#   tools/fetch.sh os       OS images only
#
# Sources (see docs/RESOURCES.md):
#   HxC2001 QuickInstall_FloppyDiskImages.zip -> SDHxCFE_Ensoniq_EPS.zip
#     EPS OS 2.2, 2.45, 2.49 and EPS-16+ OS 1.00-1.30 as .hfe
#   archive.org: EPS schematics, service bulletins, EPS-16+ schematics and
#     service manual, Advanced Applications Guide, a second copy of OS 2.49
set -e
cd "$(dirname "$0")/.."
mkdir -p build/os_versions build/refs build/hfe
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
EPSTOOL="python3 tools/epstool.py"

get() {  # url dest
    [ -s "$2" ] && return
    echo "fetch $2"
    curl -fsSL -A "$UA" --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"
}

# ---- OS images (HxC pack, ~100 MB, only the EPS zip is kept)
if [ ! -s build/hfe/EPS249OS.hfe ]; then
    get https://hxc2001.com/download/floppy_drive_emulator/QuickInstall_FloppyDiskImages.zip \
        build/QuickInstall_FloppyDiskImages.zip
    unzip -p build/QuickInstall_FloppyDiskImages.zip \
        QuickInstall_FloppyDiskImages/SDHxCFE_Ensoniq_EPS.zip > build/SDHxCFE_Ensoniq_EPS.zip
    unzip -o -q build/SDHxCFE_Ensoniq_EPS.zip 'EPS*OS.hfe' -d build/hfe
    rm build/QuickInstall_FloppyDiskImages.zip build/SDHxCFE_Ensoniq_EPS.zip
fi

$EPSTOOL hfe2img build/hfe/EPS249OS.hfe build/eps249os.img
$EPSTOOL img2ede build/eps249os.img build/eps249os.ede
$EPSTOOL extract build/eps249os.img 0 build/eps_os_249.bin
echo "01911d8f30e900892fdd1ddbc10bbc047836fb4785de6b87c8b69674edcb79e3  build/eps_os_249.bin" \
    | sha256sum -c -

# EPS 2.2 / 2.45 and EPS-16+ 1.00-1.30 (the EPS1xx files are EPS-16+ OSes)
for v in 2_2 245 100 110 119 130; do
    $EPSTOOL extract build/hfe/EPS${v}OS.hfe 0 build/os_versions/eps_os_$v.bin
done

[ "$1" = os ] && exit 0

# ---- Reference documents (archive.org)
IA=https://archive.org/download
get "$IA/sm_Ensoniq_EPS_Schematics/Ensoniq_EPS_Schematics.pdf" build/refs/Ensoniq_EPS_Schematics.pdf
get "$IA/sm_Ensoniq_EPS_Service_Bulletins/Ensoniq_EPS_Service_Bulletins.pdf" build/refs/Ensoniq_EPS_Service_Bulletins.pdf
get "$IA/eps-16plus-schematics/EPS16plus-schematics.pdf" build/refs/EPS16plus-schematics.pdf
get "$IA/sm_Ensoniq_EPS_16_Service_Manual/Ensoniq_EPS_16_Service_Manual.pdf" build/refs/Ensoniq_EPS_16_Service_Manual.pdf
get "$IA/ensoniq-eps-advanced-applications-guide/Ensoniq%20EPS%20Advanced%20Applications%20Guide.pdf" \
    build/refs/Ensoniq_EPS_Advanced_Applications_Guide.pdf
get "$IA/eps-os-v-249/EPS_OS_V249.img" build/refs/EPS_OS_V249.img

# The archive.org OS 2.49 disk must hold the same OS file as the HxC one.
$EPSTOOL extract build/refs/EPS_OS_V249.img 0 build/refs/eps_os_249_ia.bin
cmp build/refs/eps_os_249_ia.bin build/eps_os_249.bin && echo "OS 2.49: both sources identical"
