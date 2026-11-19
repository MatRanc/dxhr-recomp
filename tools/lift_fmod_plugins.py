"""Lift FMOD SPU plugin images as relocatable overlays (adapted from erikomis/afro-samurai-recomp).
usage: lift_fmod_plugins.py SPU_IMG_DIR OUT_DIR TOOLKIT_DIR [first_idx last_idx]"""
import glob, os, re, struct, subprocess, sys
imgdir, spudir, kit = sys.argv[1:4]
lo, hi = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (2, 23)
FIRST_IMAGE_ID = 40; EBOOT_TEXT_VA = 0x10000
plugs = []
for elf in sorted(glob.glob(f"{imgdir}/spu_*_at_*.elf")):
    m = re.match(r"spu_(\d{4})_at_([0-9A-F]{8})\.elf", os.path.basename(elf))
    idx, file_off = int(m.group(1)), int(m.group(2), 16)
    if not lo <= idx <= hi: continue
    e = open(elf, "rb").read()
    phoff, = struct.unpack(">I", e[28:32]); phnum, = struct.unpack(">H", e[44:46])
    text = None
    for i in range(phnum):
        p_type, p_off, p_va, _, p_filesz, _, p_flags, _ = struct.unpack(">8I", e[phoff+32*i:phoff+32*i+32])
        if p_type == 1 and p_flags & 1: text = (p_off, p_va, p_filesz); break
    if not text: continue
    stem = os.path.basename(elf)[:-4]; prefix, out = f"fmodplug_{stem}_", f"{spudir}/fmodplug_{stem}"
    subprocess.check_call([sys.executable, f"{kit}/tools/spu_lifter.py", elf, "--auto-functions", elf,
        "--symbol-prefix", prefix, "-o", out, "--reloc", "--merge-chunks",
        "--source-name", "spu_recomp.c", "--header-name", "spu_recomp.h"], stdout=subprocess.DEVNULL)
    ea = EBOOT_TEXT_VA + file_off + text[0]
    plugs.append((stem, prefix, ea, text[2], text[1]))
    print(f"{stem}: text EA 0x{ea:08X} +0x{text[2]:X}, canon 0x{text[1]:X}")
with open(f"{spudir}/fmodplug_register.c", "w") as f:
    f.write('#include <stdint.h>\nextern void spu_begin_image(int image_id);\n'
            'extern void spu_overlay_register_region_reloc(uint32_t content_ea, uint32_t span, uint32_t canon, int image_id);\n')
    for stem, prefix, *_ in plugs: f.write(f"extern void {prefix}spu_recomp_register(void);\n")
    f.write("__attribute__((constructor)) static void fmodplug_register(void)\n{\n")
    for i, (stem, prefix, ea, size, canon) in enumerate(plugs):
        img = FIRST_IMAGE_ID + i
        f.write(f"    spu_begin_image({img}); {prefix}spu_recomp_register();\n")
        f.write(f"    spu_overlay_register_region_reloc(0x{ea:08X}u, 0x{size:X}u, 0x{canon:X}u, {img});\n")
    f.write("    spu_begin_image(0);\n}\n")
print(len(plugs), "plugin(s) lifted")
