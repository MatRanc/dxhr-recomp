# dxhr-recomp

Native macOS (Apple Silicon / Metal) static recompilation of **Deus Ex: Human Revolution** (`BLES01150`, v1.01) built with [ps3recomp](https://github.com/MatRanc/ps3recomp/tree/dxhr) (`dxhr` branch, forked from `sp00nznet/ps3recomp` v0.19.0 + `afro-samurai-recomp` macOS/Metal patches).

> **Note:** No copyrighted game assets, disc dumps, decrypted executables, or lifted game C++ sources are included in this repository. You must supply your own legal copy of the game and PS3 firmware files (`dev_flash`) to reproduce the build.

See [HANDOFF.md](HANDOFF.md) for detailed technical notes, status, and debugging history.

## Status

- **Target:** Apple Silicon (M1), macOS, Metal (`BLES01150` v1.01)
- **Progress:** Boots through intro, menus, loading (~60 fps), opening cinematic, and 3D gameplay at **30.0 fps** (brief ~200–300 ms streaming hitches).

## Roadmap

- [ ] Fix asset-streaming frame-time spikes
- [ ] Add `tools/extract_jobs.py` for one-shot SPURS job extraction
- [ ] Verify progression past the opening mission
- [ ] Upstream remaining fixes to `sp00nznet/ps3recomp`
- [ ] Add gameplay screenshots

---

## Prerequisites (macOS / Apple Silicon)

- Xcode Command Line Tools
- Homebrew packages:
  ```zsh
  brew install cmake ninja sdl2 glslang spirv-cross spirv-tools
  ```
- Python 3.11+ (with a venv for `ps3recomp-afro/tools` scripts)
- [RPCS3](https://rpcs3.net/) (used for `--decrypt` on `EBOOT.BIN` and `dev_flash` firmware fonts/PRXs)
- Your own **Deus Ex: Human Revolution** (`BLES01150`) disc ISO and v1.01 patch `EBOOT.BIN`

---

## Reproducing from Scratch

### 1. Clone with Submodule

```zsh
git clone --recursive https://github.com/MatRanc/dxhr-recomp.git
cd dxhr-recomp
```

If you already cloned without `--recursive`:

```zsh
git submodule update --init --recursive
```

Create a Python virtual environment and install the toolkit's requirements if needed:

```zsh
python3 -m venv .venv
source .venv/bin/activate
pip install -r ps3recomp-afro/requirements.txt  # if present; or pyelftools/capstone/toml as needed
```

### 2. Extract Disc Data & Decrypt EBOOT

1. Extract the disc ISO into `game/PS3_GAME/`:
   ```zsh
   NODEC=1 python tools/iso_extract.py /path/to/dxhr.iso "" game PS3_GAME
   ```
   > **Gotcha:** ISO9660 Level 1 mangles `CACHE.000.md5` to `CACHE_000.MD5`. Copy it so the installer/cache check finds it:
   > ```zsh
   > cp game/PS3_GAME/USRDIR/CACHE_000.MD5 game/PS3_GAME/USRDIR/CACHE.000.md5
   > ```
2. Decrypt the v1.01 patch `EBOOT.BIN` into `work/EBOOT.elf`:
   ```zsh
   mkdir -p work
   /Applications/RPCS3.app/Contents/MacOS/rpcs3 --decrypt /path/to/BLES01150/USRDIR/EBOOT.BIN
   mv /path/to/BLES01150/USRDIR/EBOOT.elf work/EBOOT.elf
   ```
3. Create fake HDD directories (`hdd0/`, `hdd1/`). Optionally copy `BLES01150_CACHE` from RPCS3's `dev_hdd0/game/` to `hdd0/game/BLES00000_CACHE/` to skip the first-time install screen.

### 3. Lift PPU Code & Generate NIDs

```zsh
mkdir -p out recompiled
python ps3recomp-afro/tools/ppu_loader.py work/EBOOT.elf -o out/
python ps3recomp-afro/tools/ppu_lifter.py work/EBOOT.elf --hle-stubs out/EBOOT.imports.json --output recompiled/
python ps3recomp-afro/tools/gen_hle_nids.py --all --out recompiled/ppu_hle_nids.cpp
```

*(Any additional NIDs missing from stock `gen_hle_nids.py` are automatically registered at boot in `port-afro/stubs.cpp`.)*

### 4. Extract & Lift SPU Images / FMOD Plugins / SPURS Jobs

```zsh
mkdir -p spu_imgs jobdump
python ps3recomp-afro/tools/extract_spu_images.py work/EBOOT.elf -o spu_imgs
python tools/lift_fmod_plugins.py spu_imgs port-afro/spu ps3recomp-afro
```

For raw SPURS jobs: extract the 23 unique job binaries from `work/EBOOT.elf` (or capture any missing ones at runtime via `SPU_DUMP_MISS=$PWD/jobdump ./run.sh`) and lift them:

```zsh
python tools/lift_jobs.py jobdump port-afro/spu ps3recomp-afro
```

### 5. Configure & Build

```zsh
cmake -B port-afro/build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DPS3RECOMP_DIR="$PWD/ps3recomp-afro" \
  -DRECOMP_DIR="$PWD/recompiled" \
  -DPORT_SPU_INPUTS="$PWD/work/EBOOT.elf"

cmake --build port-afro/build -j8
```

### 6. Run

```zsh
./run.sh 60 run.log
```

See [run.sh](run.sh) for the required environment variables (`GCM_HANDLER_THREAD=1`, `GCM_ENGINE_3D_SUBCH=1`, `SPURS_JG_WAIT_FOREVER=1`, `PS3_DEV_FLASH`, etc.).
