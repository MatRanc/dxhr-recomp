"""Lift raw SPURS job binaries (captured with SPU_DUMP_MISS) and register them by fingerprint.
Adapted from erikomis/afro-samurai-recomp tools/lift_jobs.sh.
usage: lift_jobs.py JOB_BIN_DIR SPU_OUT_DIR TOOLKIT_DIR"""
import glob, os, re, subprocess, sys
bindir, spu, kit = sys.argv[1:4]
sys.path.insert(0, f"{kit}/tools")
from wrap_spu_elf import wrap
FIRST_IMAGE_ID = 300
jobs = []
for path in sorted(glob.glob(f"{bindir}/spujob_*.bin")):
    fp = re.match(r"spujob_([0-9A-F]{16})_", os.path.basename(path)).group(1)
    prefix, out = f"job_{fp}_", f"{spu}/job_{fp}"
    elf = f"{bindir}/{fp}.elf"
    open(elf, "wb").write(wrap(open(path, "rb").read(), base=0, entry=0))
    subprocess.check_call([sys.executable, f"{kit}/tools/spu_lifter.py", "--auto-functions", elf,
        "--base", "0x0", "--symbol-prefix", prefix, "-o", out, "--merge-chunks",
        "--source-name", "spu_recomp.c", "--header-name", "spu_recomp.h"], stdout=subprocess.DEVNULL)
    os.remove(elf); jobs.append((fp, prefix)); print("lifted", os.path.basename(path))
with open(f"{spu}/jobs_register.c", "w") as f:
    f.write('#include "spu_workload.h"\nextern void spu_begin_image(int image_id);\n')
    for fp, p in jobs:
        f.write(f"extern void {p}spu_func_00000000(spu_context*);\nextern void {p}spu_recomp_register(void);\n")
    f.write("__attribute__((constructor)) static void jobs_register(void)\n{\n")
    for i, (fp, p) in enumerate(jobs):
        f.write(f"    spu_begin_image({FIRST_IMAGE_ID+i}); {p}spu_recomp_register();\n")
        f.write(f'    spu_workload_register_img(0x{fp}ULL, {p}spu_func_00000000, {FIRST_IMAGE_ID+i}, "job_{fp}");\n')
    f.write("    spu_begin_image(0);\n}\n")
print(len(jobs), "job(s) lifted")
