# Deus Ex: Human Revolution → native macOS (ps3recomp) — handoff

Status as of 2026-11-18 (Session 7; see the Session 7 section). **The game boots cleanly past HDD cache verification, renders the intro logos, reaches the full-color Title Screen ("PRESS START"), Main Menu, New Game loading screen, 3D scene pipeline, and runs 3D gameplay locked at 30.0 fps (`+150` flips per 5 s heartbeat) across ~80 % of a 7-minute session (`run_playtest17.log`, 13,190 flips) with all 23 EBOOT SPURS jobs lifted!**
Verified via headless frame dumps (with `PAD_SCRIPT="36:0x0008,43:0x4000,49:0x4000,55:0x4000"`):
- Legal / copyright screen (`frame_qpop.ppm`), Eidos Montréal & Square Enix logos
- **Title Screen ("DEUS EX: HUMAN REVOLUTION — PRESS START")** (`frame_menu_boom.png`, 130 draws/frame, 0 dropped draws)
- **New Game loading screen** (`frame_ingame_test.png`, ~60 fps during load)
- **3D scene + opening cinematic with subtitles** (`frame_3d_first.png`, 78% non-zero, 9 render targets including 1280×720 HDR/tonemap + 640×360 / 320×180 bloom/SSAO, 23+ 3D MSL shaders compiled & cached in `cache/msl`, 0 missing SPU jobs, 0 unresolved NIDs).

**Current status:** **Smooth 30.0 fps in menus, cinematics, and most 3D gameplay on Apple Silicon Metal!** In `run_playtest17.log` (7-minute run, 13,190 flips, 150 KB total log), menus/early scenes ran for 24 consecutive 5 s heartbeats at a locked 30.0 fps (`+150` flips/5 s) and 3D gameplay ran for 17 consecutive 5 s heartbeats at a locked 30.0 fps (`+149`–`+150` flips/5 s). The only remaining hiccups are brief ~200–300 ms frame-time spikes during asset-streaming bursts (`[sem] create ... lr=0x00B557D8` + `ResolveDecompressor` one-shot SPURS chains); see **Session 8 — start here** below.

- Title: Deus Ex: Human Revolution, EU disc `BLES01150`, v1.01 patch EBOOT
- Toolkit: [sp00nznet/ps3recomp](https://github.com/sp00nznet/ps3recomp) v0.19.0 (`ae92407b`)
- Host: Apple M1, macOS, Metal. Upstream says macOS cannot run a retail title from the stock tree yet.
- Closest working reference: [erikomis/afro-samurai-recomp](https://github.com/erikomis/afro-samurai-recomp)
  (macOS/arm64, Metal, reaches gameplay, also an FMOD game). Copies of its scripts and patch are in `ref/`.

## Layout (`~/Documents/ps3/dxhr-recomp/`)

| Path | What |
|---|---|
| `run.sh [secs] [log]` | Runs the port with all env vars found so far. Uses SIGKILL timeout (the game ignores SIGTERM). |
| `port-afro/` | **The port you want.** Template project + FMOD/job SPU sources, built against `ps3recomp-afro`. Build: `cmake --build port-afro/build -j8`. |
| `ps3recomp-afro/` | Git worktree of the toolkit at `ae92407b` + Afro patch (`ref/afro.patch`) + my edits (below). 48 uncommitted files. |
| `ps3recomp/` | Stock clone, branch `dxhr-local` (merged PRs #712 #725 #800 #787 #808 #797 #723). `port/` is its build. **Older; superseded by the afro tree.** Has the Python venv `.venv` used by all tools. |
| `recompiled/` | Lifted PPU C++ (29 chunks, 53,589 functions, 1.4 GB). Do not regenerate lightly (see gotchas). |
| `work/EBOOT.elf` | Decrypted patched EBOOT. `out/` = loader JSON. `spu_imgs/` = 24 extracted SPU ELFs. |
| `game/PS3_GAME/` | Extracted disc (7.9 GB). `hdd0/ hdd1/` = fake HDD roots. |
| `jobdump/` | All 23 unique raw SPURS job binaries extracted from `work/EBOOT.elf` (all lifted in `port-afro/spu/`). |
| `tools/` | `iso_extract.py`, `lift_fmod_plugins.py`, `lift_jobs.py` (mine). |
| `ref/` | Afro's README, scripts, patch. `prs_open.json` = upstream open PRs. |

## Reproducing from scratch

1. **EBOOT:** the ISO is an encrypted-looking 3k3y image but its data is already decrypted. The v1.01 patch is
   in RPCS3 (`~/Library/Application Support/rpcs3/dev_hdd0/game/BLES01150/USRDIR/EBOOT.BIN`).
   `/Applications/RPCS3.app/Contents/MacOS/rpcs3 --decrypt EBOOT.BIN` → `EBOOT.elf`.
2. **Loader / lifter / NIDs** (stock tool commands, in the venv):
   `python tools/ppu_loader.py work/EBOOT.elf -o out/`, then `ppu_lifter.py ... --hle-stubs out/EBOOT.imports.json --output recompiled/`,
   then `gen_hle_nids.py --all --out recompiled/ppu_hle_nids.cpp`. Lifting takes ~2 min.
3. **Disc data:** `NODEC=1 python tools/iso_extract.py <iso> <dkey> game PS3_GAME`. (The key is unused with `NODEC=1`.)
   Large files are multiple ISO extents; the script appends them (an earlier bug truncated every big file).
4. **SPU:** `extract_spu_images.py work/EBOOT.elf -o spu_imgs`, configure with
   `-DPORT_SPU_INPUTS=work/EBOOT.elf` (lifts the 24 images at configure time), then
   `python tools/lift_fmod_plugins.py spu_imgs port-afro/spu ps3recomp-afro` (images 2–23 as relocatable overlays)
   and `python tools/lift_jobs.py jobdump port-afro/spu ps3recomp-afro` (raw job binaries).
   New missing jobs show up as `no lifted image` in the log: run with `SPU_DUMP_MISS=$PWD/jobdump ./run.sh`, re-lift, rebuild, repeat.
5. **Build:** `cmake -B port-afro/build -G Ninja -DPS3RECOMP_DIR=…/ps3recomp-afro -DRECOMP_DIR=…/recompiled -DPORT_SPU_INPUTS=…/work/EBOOT.elf`
   then `cmake --build`. Needs `brew install cmake ninja sdl2 glslang spirv-cross spirv-tools` (without glslang the log says "guest shaders off" → black).
   `port-afro/CMakeLists.txt` has my added blocks that glob `spu/job_*` and `spu/fmodplug_*`.

## Run settings that matter (all in `run.sh`)

`GCM_HANDLER_THREAD=1` — **required.** Without it the VBlank handler only runs when a guest thread makes an HLE call/sleeps, and the main
thread sits in `sys_semaphore_wait(SemWVBL)` forever. Also: `PS3_VFS_ROOT=game`, `PS3_HDD0_ROOT`, `PS3_HDD1_ROOT`,
`PS3_DEV_FLASH=~/Library/Application Support/rpcs3/dev_flash` (from Afro), `GCM_ENGINE_3D_SUBCH=1`, `SPURS_JC_JOBLIST_PAR=4`,
`SPURS_JG_WAIT_FOREVER=1` (required for `Rendering` / `ShaderPatch` ring job chains).
Debug env vars worth knowing: `SEMTID=1` (semaphore waits with tid/lr), `PS3_HLE_TRACE=N`, `HLE_BT_EVERY=1` (guest stack at each import),
`SPU_DUMP_MISS=dir`, `PS3_FSLOG=1`, `PS3RECOMP_METAL_HEADLESS=1 PS3RECOMP_METAL_FRAME_DUMP=<file.ppm>`.

## What I fixed, in order (so you know what is already solved)

1. Black window + hang → `GCM_HANDLER_THREAD=1` (above).
2. Truncated disc files → `iso_extract.py` multi-extent bug. This caused `Out of memory, "Misc" requested 0xae7794ec bytes`.
3. `Failed to open contentupdate1.000.edat` fatal → `libs/network/sceNp.c` (`ps3recomp-afro`): DRM availability now returns ENOENT for files not under `PS3_HDD0_ROOT`.
4. `sys_prx_register_library` was unresolved → stub in `runtime/ppu/ppu_sysprx.cpp` (afro tree and stock tree).
5. FMOD mixer branched into unlifted LS `0x25988` → plugin overlays (`lift_fmod_plugins.py`).
6. Guest shaders off → installed glslang/spirv-cross.
7. Five SPURS job binaries (576, 816, 19,776, 73,968, 79,232 bytes) → `lift_jobs.py`.

## Session 3 (2026-11-18 late evening) — first picture achieved!

All four causes of the unpatched FIFO jump-park (`0x2AB0` → `0x7DE0` → `0x9D80` → `0x235B0`) and boot OOM race were found and fixed:

1. **SPU `$sp` word-1 stack-check ABI (`ps3recomp-afro/runtime/spu/spurs_job.c`):** `ShaderPatch` (image 303) was hitting
   `HALT-ASSERT heqi pc=0x01798` on its very first frame because `spurs_job.c` only initialized `ctx.gpr[1]._u32[0]` (`SP`)
   and left `_u32[1]` (available stack bytes checked by `ai $sp,$sp,-N; xswd; heqi -1`) at 0. Setting `_u32[1] = sp - (s_ls + size_scr)`
   eliminated the halt-assert completely.
2. **Ring job-chain persistence & race-free handoff (`ps3recomp-afro/libs/spurs/cellSpurs.c`, `run.sh`):**
   - `Rendering` (`jc=0x11216F00`) uses a 2-slot ping-pong ring with `END` (`0x7F`) markers and reuses the same static job descriptor
     (`0x11217200`). `ShaderPatch` (`jc=0x1120C300`) parks on self-`NEXT` (`pc | 3`) and `END`, and is what DMAs the `JUMP` patches over
     the FIFO jump-parks (`SPU_WATCH_FIFO=1` confirmed `[spu-fifo-put] img=303 ea=0x10002AB0 size=4 w0=0x25450AC0`).
   - Added `SPURS_JG_WAIT_FOREVER=1` to `run.sh`, added condvar parking for self-`NEXT` alongside `END`, and made `jc_start` wake
     a running chain via `pthread_cond_broadcast` and wait (50 ms cap) until the walker reaches an unchanged park point.
3. **`ShutdownJobChain` / `JoinJobChain` race (`ps3recomp-afro/libs/spurs/cellSpurs.c`):** `cellSpursShutdownJobChain` previously
   cleared `running = 0` immediately instead of signaling a `shutdown_req` flag, so `cellSpursJoinJobChain` returned while
   `ResolveDecompressor` was still decompressing and the PPU read garbage allocation sizes → intermittent `Out of memory, "Misc"` crash.
   Fixed by adding `shutdown_req` and only clearing `running = 0` when `jc_thread` drains through `END` and exits.
4. **Implemented `cellSpursQueuePopBody` (NID `0x91066667`):** `Rendering` (image 302) was spinning forever at `pc=0x09428` calling
   `cellSpursQueueTryPushBegin` (`0x116D8`) once its depth-32 `CellSpursQueue` (`0x16372080`) filled up after ~17 frames because the PPU
   consumer's `cellSpursQueuePopBody` was an unresolved import. Implemented in `ps3recomp-afro/libs/spurs/cellSpurs.c` and registered
   `0x91066667` in `recompiled/ppu_hle_nids.cpp` (**gotcha:** re-running `gen_hle_nids.py` will need `cellSpursQueuePopBody` in the
   generator or re-added to `ppu_hle_nids.cpp`).

5. **Fixed Scaleform AMP 3 s/frame stall (`recompiled/ppu_hle_nids.cpp`):** Unresolved BSD `sys_net` aliases `listen`
   (`0x28E208BB`), `accept` (`0xC94F6939`), and `send` (`0xDC751B40`) returned positive garbage in `r3`, tricking Scaleform AMP
   (`GFxAmpServer`) into thinking a remote profiler client had connected and blocking the main thread in `func_008D65F4`
   (`sys_cond_wait(1000 ms)` × 3) every frame. Registered all three to `sys_net_bnet_listen` / `accept` / `send` (returning `-1`
   offline). Frame pacing is now a steady **~31 fps** (738 flips in 30 s) and the game advances past the logos to the full-color
   **Adam Jensen "Installing..." screen**.

## Session 4 (2026-11-18 late night) — HDD cache check passed, 6th SPU job lifted, Eidos & Square Enix logos verified

1. **Fixed `cellGameDeleteGameData` guest-pointer crash (`ps3recomp-afro/libs/system/cellGame.c` ~L781–788):** Translated `dirName`
   via `vm_base + ea` before `printf` (previously segfaulted when the game tried to clean up a broken cache dir).
2. **Fixed disc cache verification / install loop:**
   - ISO9660 Level 1 had mangled `CACHE.000.md5` to `CACHE_000.MD5` on disc, causing the installer to stall at 99% and reject the
     cache on reboot. Copied `game/PS3_GAME/USRDIR/CACHE_000.MD5` → `game/PS3_GAME/USRDIR/CACHE.000.md5`.
   - Populated `hdd0/game/BLES00000_CACHE/` with `CACHE.000` (2.0 GB), `CACHE.001` (852 MB), `CACHE.000.md5` (66 B), `ICON0.PNG`,
     and `PARAM.SFO` from RPCS3's `BLES01150_CACHE`. The game now verifies both MD5s cleanly and skips the first-time install screen.
3. **Lifted 6th SPURS job binary (`spujob_24B0B89749563CA8_9408.bin`, 9,408 bytes, owner `0x11217080`):**
   - Captured with `SPU_DUMP_MISS=$PWD/jobdump`, lifted via `ps3recomp/.venv/bin/python tools/lift_jobs.py jobdump port-afro/spu ps3recomp-afro`.
   - **Important CMake gotcha:** Adding a new job in `port-afro/spu/` triggered a CMake reconfigure that overwrote the custom FMOD
     mixer lift in `port-afro/build/generated_spu/spu_64b58525bd23db5e1be4f002971eb8809ac96aa03a0e06fb1f298fbd7da0e6ca/`. We re-lifted
     the FMOD mixer in-place with `--base 12288 --return-entries --merge-chunks` and rebuilt. Wire this into `PS3RecompSPU.cmake` so
     future reconfigures don't lose it.
4. **Verified intro logos in headless mode (`RSX_ENGINE_PASS_DUMP` / `PS3RECOMP_METAL_FRAME_DUMP`):**
   - ~20 s in: **Eidos Montréal** logo (1280×720, crisp, 4.06% non-zero).
   - ~22 s in: **Square Enix** logo (1280×720, crisp white+red, 2.14% non-zero).
   - Game runs at steady **~31 fps** (`guest flips` advancing continuously, Scaleform display list rendering on main thread, 0 FIFO
     jump-park resyncs, 0 missing SPU jobs).

## Session 5 (2026-11-18 night) — Title Screen, Main Menu, New Game, 3D pipeline & opening cinematic!

1. **Root-caused & fixed post-logo black screen (`ps3recomp-afro/libs/spurs/cellSpurs.c`):**
   - Once the Title Screen / Main Menu exceeded 16 Scaleform draws (65–130 draws/frame), `func_00228F34` offloaded draw-list sorting
     to SPU job `0x11217080` (`24B0B89749563CA8`) and read the sorted head back via `CellSpursQueue` (`0x16372080`). Two bugs broke this:
     - **`_cellSpursQueueInitialize` struct layout:** Wrote `size`, `depth`, `buffer` at `+0x10`, `+0x14`, `+0x18` instead of the
       PS3 SDK layout (`+0x08` = `size`, `+0x0C` = `depth`, `+0x10` = `u64 buffer`, `+0x18` = `eventPort` `0xFFFFFFFF`, `+0x1C` = `direction`).
       SPU `cellSpursQueueTryPushBegin` was DMAing `size=0` to `ea=0x20` (MFC rejected), leaving the queue buffer all zeros so
       `drawList->head` became `NULL` and all 65–130 draws vanished every frame. Updated `_cellSpursQueueInitialize`, `PushBody`, and `PopBody`.
     - **`cellSpursQueuePopBody` 4-arg ABI:** Added missing `isPeek` (`r5`) parameter before `isBlocking` (`r6`). Previously `isPeek=0`
       was misread as `isBlocking=0`, returning `BUSY` immediately instead of waiting for the SPU sorter.
2. **Fixed `1x1` surface clobber (`ps3recomp-afro/libs/video/rsx_draw_engine.c`):**
   - `eng_current_target_set` now returns `0` when `sf.color_target == CELL_GCM_SURFACE_TARGET_NONE`.
   - `eng_present` capture log no longer calls `eng_current_surface()` (which mutated the surface table) and prints per-reason `sink_end` drop stats.
3. **Rate-limited `AddressToOffset REFUSED` spam (`ps3recomp-afro/libs/video/cellGcmSys.c`):**
   - Verified via guest backtraces that `ea=0` comes from `func_00274648` converting an optional NULL secondary vertex stream pointer (benign).
   - Rate-limited log output to first 10 + every 10,000th call.
4. **Registered remaining unresolved NIDs (`recompiled/ppu_hle_nids.cpp`):**
   - Wired `cellKbRead` (`0xFF0A21B7`) and `inet_addr` (`0xDABBC2C0` → `sys_net_bnet_inet_addr`). Zero unresolved NIDs through opening cinematic.
5. **Wired FMOD mixer `--return-entries --merge-chunks` permanently into CMake:**
   - Added `--return-entries` support to `ps3recomp-afro/tools/build_spu_workloads.py`, `spu_program_pipeline.py`, and
     `cmake/PS3RecompSPU.cmake` (`PS3RECOMP_SPU_RETURN_ENTRIES`), set for `spu_64b58525bd23db5e1be4f002971eb8809ac96aa03a0e06fb1f298fbd7da0e6ca`
     in `port-afro/CMakeLists.txt`. Verified across multiple CMake reconfigures (`370 call return address(es), 1108 -> 1439 bound(s)`).
6. **Extracted & lifted ALL 23 unique raw SPURS job binaries from `work/EBOOT.elf`:**
   - Scanned `work/EBOOT.elf` for the SPURS job header (`44012850 32000080 44012850` at `+0x10`) and matched exact sizes from the `.data`
     `(vaddr, size)` table (all 9 previously runtime-dumped jobs verified bit-for-bit). Lifted all 23 via `tools/lift_jobs.py` and rebuilt.
7. **Updated `run.sh`:** Defaulted `PS3_MOUSE_CAPTURE=0 PS3_MOUSE=0` and `SPU_DUMP_MISS=$PWD/jobdump`.

## Session 6 (2026-11-18 night) — freeze, depth-only passes, job-chain parallelism

1. **False SPU halt (gameplay freeze) — `runtime/spu/spu_dma.h`:** the repeat-transfer watchdog now restarts its episode when two
   identical transfers are >5 ms apart (a wedged loop repeats every ~1 ms; job 322 does one PUT per frame). Resetting from
   `spurs_job.c` would not work: the counter is a function-static in a header, one copy per lifted-job TU.
2. **Missing scene geometry (flat tan screen, only moving parts drawn) — `libs/video/rsx_draw_engine.c`:** Session 5's
   `TARGET_NONE` early return in `eng_current_target_set` dropped every depth-only clear and draw, so depth kept the previous
   frame and DX:HR's LESS pre-pass / EQUAL material pass drew only what moved. Found with a live pass dump (`passdump/`, pass 0:
   full depth, almost no colour). Depth-only passes now bind a private scratch colour target (`ENG_SCRATCH_LOCATION` 0x7F, keyed by
   size), never presented/sampled/read back. The opening shot has no depth-only work (`tgt=0`), which is why headless dumps looked fine.
3. **Gameplay fps — `libs/spurs/cellSpurs.c`:** `SPURS_JC_JOB_PAR=<n>` runs consecutive JOB commands (no SYNC between) on up to n
   threads, capped by the chain's `maxContention` (now stored per chain). Image 318 (~100 skinning jobs/frame) was walked serially
   while the render thread waited in `cellSpursRunJobChain`. In-game 9–15 → 15–25 fps. `SPURS_JC_JOB_PAR=0` to A/B.
4. **Log-lock hitches — `run.sh`:** `PS3_VERBOSE=0` by default (a redirected stderr made the runtime log two flushed lines per SPU
   job through one lock; 83 MB per session). Set `PS3_VERBOSE=1` for the per-job lines.
5. **HUD:** `PS3_OVERLAY_HUD=1 PS3_OVERLAY_HUD_GRAPH=1` on by default (fps, frame time, graph; F1 menu).
6. **`sys_prx_load_module` (NID 0x26090058)** stubbed to `CELL_PRX_ERROR_UNKNOWN_MODULE` (game's encrypted `DFENGINE.SPRX`; same
   not-loaded path the default `CELL_OK` fake already took).
7. **Pass capture on demand:** `RSX_ENGINE_PASS_DUMP=$PWD/passdump RSX_ENGINE_PASS_DUMP_TRIGGER=$PWD/capture ./run.sh ...`, then
   `touch capture` when the scene is on screen (`rm capture` before the next run).
8. Ruled out: GPU frames-in-flight (sync-present experiment, removed), overlay INI (none), window resolution.

9. **Dark environment (characters lit, world black) — `rsx_draw_engine.c` `eng_zdepth_as_color`:** environment shaders sample
   the shadow atlas (t14, zeta 0:0x01D80000, Z16, UN) declared 3072x3072 while only 3072x1024 is drawn (21 draws, vp/scissor
   0,0 1024x1024 — confirmed via the new per-draw `clip/vp/sc/wo` fields in `draws.txt`). The GPU depth->colour path refused
   (texture taller than drawn), so reads fell back through guest memory, which for RSX local memory is not backed -> depth 0 ->
   everything shadowed. UN textures now bind the drawn part (the shadow helper normalizes by the bound size). Character shaders
   (pipes 289/294) don't sample t14, which is why only they were lit. **Unverified in game.**
10. **Frame pacing — `port-afro/main.cpp` frame clock:** vblank is now exact 59.94 Hz on a steady µs clock (was 16 ms = 62.5 Hz,
   game 4.3 % fast, 31.25 fps cap that judders on 60 Hz) and the loop sleeps to the next tick instead of a flat `Sleep(4)`.
   `PS3_VBLANK_HZ` overrides.
11. **Double present — `rsx_draw_engine_present`:** the frame clock presented every guest flip before draining to its 0xE944, so
   each frame went out twice (old buffer, then new via `sink_flip`), ~62 vsync-blocking presents/s on the FIFO/vblank thread.
   Now a no-op once the FIFO has carried a flip.
12. **SPU MFC registry lock contention** (found by a parallel session's profile, ~600 samples in `mfc_for`/`spu_wrch`):
   `SPU_MFC_LOOKUP_CACHE=1` on by default in `run.sh` (existing per-thread cache; skips the global SRW lock on hits).

13. **Black environment, root cause (run 10 capture, `./run.sh diag` + `./capture.sh`):** environment shaders multiply their
   colour by the AO in the alpha of the normals buffer (0x03320000, `tex5.w`); the AO chain (pipes 26-30, 640x360 targets
   0x00F40000/0x01021000) was garbage (decoded half-floats of +-512). Two decompiler/texture bugs:
   a. **H/R register aliasing missing** (`rsx_fp_decompiler.c` `fp_alias_sync`): NV40 H(2n),H(2n+1) alias R(n), .x in the low
      16 bits. The SSAO writes view depth to H0.xy then `UP4UB R0.x`; r[] and h[] were separate arrays. Every write is now
      mirrored into the aliased register (unused mirrors are dead code for the shader compiler).
   b. **`Y16_X16_FLOAT` (0x9F) component order** (`rsx_texture_layout.c`): `.x` is the low half (second u16 in big-endian
      memory); it returned the first. 0x95/0x98/0x99 left as they were.
   Also: shadow helper returns lit (not NaN) for a zero-size map / non-finite coordinate; per-draw `fpc` constants and
   `clip/vp/sc/wo` in `draws.txt`. Verified offline: re-decompiled pipe 26 from `shaderdump/pipe26.fp.bin` translates through
   glslang + spirv-cross. **Not yet verified in game.**
14. Run 10 gameplay held 26-30 fps (30 = game cap). The capture-time profile is dominated by the pass dump itself; without it
   the FIFO/engine thread is ~1/3 busy.

15. **Shader-compile hitches (runs 11-12: 159 compiles in one minute = 10 s freeze on entering the lab, 68 more = 6-14 fps
   while moving):**
   a. Alias mirrors pruned by per-component backward liveness (`fp_alias_prune`; branchy programs keep any-read pruning):
      shader text back to +5-15 % (was ~2x). Mirror lines end in `//AS`.
   b. **Async pipeline compiles** (`rsx_metal_backend.m` `eng_pipeline_create`, `PS3RECOMP_METAL_ASYNC_SHADERS`, default on
      when windowed): HLSL->MSL, Metal library and PSO build on a serial dispatch queue; draws on a pipeline still compiling
      are skipped (pop-in for a few frames instead of a stall). `s_eng_compile_lock` serializes every translation (shared
      `s_msl`/`s_log`); `s_eng_pipe_gen` drops results after a table reset. Unverified in game.

16. **Job-chain kicks async** (`cellSpurs.c` `jc_sync_kick`, `SPURS_JC_SYNC_KICK`): the 50 ms "wait until the walker parks"
   in `jc_start` (Session 3) now applies only to the listed chains; `run.sh` sets `Rendering,ShaderPatch`. Unset = old
   behaviour (every chain waits). Chain names are kept from `CreateJobChainWithAttribute`. Profile before: render thread
   ~50 % in `cellSpursRunJobChain -> jc_start` waiting on AnimJob/Scene chains; after: it no longer shows waiting.
17. **Hybrid shader compile:** a pipeline whose two programs are already translated (memory or `cache/msl`, new
   `rsx_hlsl_to_msl_cached()`) builds synchronously; only never-seen programs go async, on the global concurrent queue.
   `eng_function` translates under `s_eng_compile_lock` and runs the Metal compile outside it. Fixed the beige/untextured
   surfaces (material pipelines skipped while queued) — user: "textures look better loading-wise".

### Session 6 playtest results (end of session)

| Run | Change under test | Result |
|---|---|---|
| 5 | parallel JOB runs | in-game 9-15 -> 15-25 fps |
| 6-8 | depth-only pass fix | whole scene geometry renders; lighting dark |
| 10 | (diag capture) | gameplay 26-30 fps in that scene; environment black (AO chain) |
| 11 | H/R aliasing + Y16_X16F order | **lighting fixed** (user confirmed); big compile hitches (283 recompiles) |
| 13 | async compile | no freezes, but pop-in / beige surfaces; 12-18 fps in the lab corridor |
| 14 | async kicks + hybrid compile | textures OK; still 12-18 fps in-game, pacing very choppy |

**User's verdict at end of session: lighting fixed; performance still bad in gameplay ("half speed", "pacing so chopped").**
Menus/cinematics: locked 29-30 (game cap at 59.94/2).

### Session 7 — performance, audio & frame-pacing overhaul (verified in `run_playtest15.log`–`run_playtest17.log`)
Profile of run 14 at ~13 fps (`sample_lag2.txt`, parsed via `scratch/samp.py`; note the user reports `sample` itself
disturbs the game — don't profile their live session unprompted; use `./capture.sh` when they ask):
- FIFO/draw-engine thread (`frame_clock`) ~62 % busy (10 % in `rsx_draw_engine_guest_read` GPU sync for 0x9F); FMOD mixer ~89 %;
  main PPU thread ~57 % busy + ~26 % waiting on the Display Frame Thread lwmutex + ~15 % `usleep(10)` polling (`func_001882B4`);
  skinning jobs ~52 % busy + ~22 % on `s_mfc_claim_lock` rwlock.

**Implemented, built in `port-afro/build/MyGameRecomp`, and playtested:**
1. **Direct per-context MFC slot pointer (`runtime/spu/spu_context.h`, `runtime/spu/spu_channels.c`):** Added `void* mfc_slot`
   to the end of `spu_context`. `mfc_for` returns `&((spu_mfc_slot*)ctx->mfc_slot)->mfc` directly without touching the global
   `s_mfc_claim_lock` SRW lock or the generation counter that `spu_mfc_release` previously invalidated across all threads after
   every job (~631 rwlock samples in `sample_lag2.txt`).
2. **Thread-local `spu_context` reuse + O(1) job fingerprint cache (`runtime/spu/spurs_job.c`, `runtime/spu/spu_workload.c`):**
   `spu_run_spurs_job` now reuses a thread-local `spu_context` (instead of `calloc(256 KB)` + 270 KB stack copy + `free` on every
   SPURS job, ~200+ times/frame), and `spu_workload_fingerprint_cached` uses a 32-slot cache with an O(1) 16-byte head/tail verify
   instead of hashing all 79 KB of the skinning binary on every job dispatch.
3. **Persistent SPURS parallel helper thread pool (`libs/spurs/cellSpurs.c` `jc_run_list_parallel`):** Replaced per-run
   `CreateThread` + `usleep(20)` join with a persistent pool of `JC_POOL_HELPERS` threads woken and joined via per-helper
   condvars (`s_jc_pool`).
4. **Per-chain mutex & condvar (`libs/spurs/cellSpurs.c`):** Replaced the single global `s_jc_mtx` / `s_jc_cond` (where every kick
   broadcast-woke all ~10 parked chain walkers) with per-chain `s_jobchains[i].mtx` and `s_jobchains[i].cond`.
5. **Sub-200 µs `sys_timer_usleep` yield-spin on macOS (`runtime/syscalls/sys_timer.c`):** Short `usleep(10)` calls (used by
   `func_001882B4` on the main and Display Frame threads to poll for synchronous SPU job completion) now yield-spin to an exact
   `host_monotonic_ns()` deadline instead of calling `nanosleep` (which added ~50–200 µs scheduler slack per poll iteration).
6. **GPU reinterpretation of RGBA8 surfaces sampled as `Y16_X16_FLOAT` (`0x9F`) (`libs/video/rsx_draw_engine.h`,
   `libs/video/rsx_draw_engine.c`, `libs/video/rsx_metal_backend.m`):** Added `color_as_y16x16f` (`ENG_REC_COLOR_Y16X16F` +
   `eng_color_y16x16f_fs` fragment shader rendering `MTLPixelFormatRG16Float` with resource 0 = Y `(A<<8)|R`, resource 1 = X
   `(G<<8)|B` as IEEE 754 half bits), cached per surface on `y16_conv` / `y16_serial` and bound via `surface_view`. Eliminates
   the ~4x/frame `submit_and_wait` full GPU sync + CPU readback/decode in the SSAO chain.
7. **Pitch-aware surface aliasing (`libs/video/rsx_draw_engine.c` `eng_surface_get`, `sink_bind_textures`):** A surface at the
   same `(location, offset)` with a different pitch (such as `0:0x01021000` alternating between `640x360` pitch 2560 and
   `320x180` pitch 1280 every frame) now gets its own surface slot instead of destroying and reallocating the Metal texture twice
   a frame, and `sink_bind_textures` selects the most recently written surface (`color_serial`) at that offset.
8. **`vmx_vmaddfp` / `vnmsubfp` arm64 hardware FMA (`runtime/ppu/ppu_vmx.h`):** Added `|| defined(__ARM_FEATURE_FMA)` to
   `vmx_fmaf` and rebuilt all 29 PPU chunks so all 3,090 VMX FMA call sites inline to arm64 `fmadd` instead of out-of-line
   double-precision emulation (~17 % of main PPU thread busy time).
9. **Eliminated `ResolveDecompressor` re-registration log flood & `JoinJobChain` busy-spin (`libs/spurs/cellSpurs.c`,
   `libs/input/cellPad.c`, `libs/misc/cellKey2char.c`):** Preserved `run_count` across chain re-registrations, capped
   `_JobChainAttributeInitialize` / `SetName` / `CreateJobChainWithAttribute` / `cellPadSetPortSetting` / `cellKey2charClose`
   logs to 16 lines (eliminating ~23,900 lines of log I/O during streaming in `run_playtest15.log`), and switched
   `cellSpursJoinJobChain` from `usleep(0)` spinning to waiting on `s_jobchains[i].cond`.
10. **Exact 5.33 ms audio block clock + interactive QoS (`libs/audio/cellAudio.c`, `runtime/spu/spu_workload.c`):** The POSIX
    `audio_mix_thread_func` previously used `usleep(2000)` / `usleep(5000)`, which drained the audio ring at ~230 blocks/s
    whenever SDL's queue dipped under 4 blocks — outrunning the guest FMOD mixer (which produces 187.5 blocks/s) and reading
    zeroed blocks (audible jumps/dropouts). Now paced to the exact monotonic 48 kHz / 256-sample deadline (5,333.33 µs/block)
    with `QOS_CLASS_USER_INTERACTIVE` on both the audio mix thread and async SPU task threads.
11. **6 ms async shader compile grace window (`libs/video/rsx_metal_backend.m` `eng_pipeline_create`):** When an uncached shader
    pipeline is dispatched to `s_eng_compile_q`, `eng_pipeline_create` waits up to 6 ms for it to finish before returning.
    Single new shaders finish within the same frame (preventing 1-frame missing-draw flicker), while large shader bursts still
    spill to the background queue without freezing the game. Also reduced the SPURS parked-chain fallback poll timeout from
    5 ms back to 0.5 ms.

### Session 7 playtest results (`run_playtest15.log`–`run_playtest17.log`)

| Run | Change under test | Result |
|---|---|---|
| 15 | fixes 1–8 (MFC ptr, TLS SPU ctx, job pool, GPU 0x9F, pitch surface, arm64 FMA) | In-game climbed from 12–18 fps to 22–30 fps (35 heartbeats at `+143`–`+151` flips/5 s); user: "working really well" |
| 16 | fix 9 (log flood + `JoinJobChain` condvar) | User: "buttery smooth in the menus... like 90% there", with minor audio jumpiness / shader flicker & occasional ~300 ms spikes |
| 17 | fixes 10–11 (exact 5.33 ms audio clock + 6 ms shader grace + 0.5 ms SPURS park poll) | **Locked 30.0 fps (`+150` flips/5 s) for ~80 % of the 7-min run (13,190 flips, 150 KB log):** 24 straight heartbeats at `+150` in early scenes, 17 straight heartbeats at `+149`/`+150` in late 3D gameplay; brief dips (`+101`–`+138` flips/5 s) only during asset-streaming bursts |

### Session 8 — start here (remaining brief ~200–300 ms streaming hiccups in `run_playtest17.log`)

1. **Every single frame-rate dip in `run_playtest17.log` (flips 7084, 8383–8877, and 12890) coincides with a burst of
   `[sem] create id=5..8 name='' init=0 max=65535 id_out=0x18894xxx lr=0x00B557D8`:**
   - `lr=0x00B557D8` is inside the game's streaming / decompression subsystem creating and destroying short-lived semaphores for
     streaming batches (paired with `ResolveDecompressor` SPURS job chains at `jc_ea=0x0107DB80` / `0x0107DD00` / `0x0107E180`).
   - **Why `ResolveDecompressor` adds latency per streaming chunk (`libs/spurs/cellSpurs.c`):**
     - Because `SPURS_JG_WAIT_FOREVER=1` is set in `run.sh` (needed only for the persistent `Rendering` and `ShaderPatch` ring chains!),
       *every* job chain — including one-shot `ResolveDecompressor` chains (`autoReadyCount=1`, `is_bb=0`, created, run once, shut down,
       joined, and re-created hundreds of times during room streaming) — parks at `END` (`0x7F`) in `jc_execute` waiting for
       `cellSpursShutdownJobChain` instead of exiting at `END`, and spawns a brand-new `CreateThread(jc_thread)` on every chunk!
     - **Fix to try first:** Make `SPURS_JG_WAIT_FOREVER` apply **only** to persistent ring chains (or chains listed in
       `SPURS_JC_SYNC_KICK` / chains that are NOT `ResolveDecompressor`), OR reuse a persistent worker thread per `s_jobchains[i]`
       slot instead of calling `CreateThread` + `WaitForSingleObject` / `CloseHandle` on every `ResolveDecompressor` streaming chunk.
   - Also inspect `func_00B557D8` (around `0x00B557D8` in `recompiled/`) and silence `[sem] create` after the first 16 calls in
     `runtime/syscalls/sys_semaphore.c`.
2. **Optional next steps:**
   - Per-draw CPU in `sink_end` (`eng_texture_slot`, `rsx_vertex_remap_build`, `rsx_vertex_fetch_many`) if dense scenes ever dip below 30 fps outside of streaming bursts.
   - Unlock the game's 30 fps cap (needs a game patch; Ghidra offered by the user).

### How to test / capture (user runs these; don't launch the game yourself)
- `./run.sh 900 run_playtestN.log` — normal play (HUD on: fps, frame time graph).
- `./run.sh diag 900 log` then `./capture.sh` in the scene — pass dump (+ per-draw constants, shaders in `shaderdump/`)
  and a 5 s CPU profile `sample_capture.txt`.

Still open: see "Session 8 — start here" above. The user does the in-game testing — do not launch the game yourself.

### Session 5 next steps (kept for history) — bugs caught during live gameplay playtest!
1. **Fix the gameplay freeze (`ps3recomp-afro/runtime/spu/spu_dma.h:1345–1380` — root cause ALREADY FOUND!):**
   - `run_playtest.log` froze at `guest flips=9782` immediately after:
     `[spu-dma] img=322 pc=0x00060: 256 identical transfers to ea=0x1121AD40 -- halting the SPU`
   - `img=322` (`job_F7B1DDEC9C8A957E`, 560 B) is NOT spinning — it does **one single 16-byte `MFC_PUT`** per frame and returns immediately (`SPU_RET`).
   - Because `t_rep` (`last_ea`, `last_lsa`, `rep`, `since`) is a `SPU_THREAD_LOCAL` variable in `spu_dma.h:1345` that is **never reset between SPURS job invocations**, after 256 frames + 30 seconds on the same worker thread, `spu_dma.h` falsely triggers `spu_halt(spu)` and kills the completion-flag job, permanently wedging the frame!
   - **Fix:** Expose a tiny `spu_dma_reset_repeat(void)` (or store `rep`/`since`/`last_ea`/`last_lsa` on `spu_context` instead of a persistent thread-local!) so every `spu_run_spurs_job()` starts with a fresh counter. Also note: `t_rep` should ideally only watch `GET`/`GETLLAR` polling loops, not one-shot `PUT`s!
   - Frozen thread sample saved at `sample_freeze.txt` (keep if needed, or delete once verified).
2. **Fix 3D gameplay lag & check missing UI / rendering:**
   - **Per-frame Metal surface thrashing spotted in `run_playtest.log`:** `surface 0:0x01021000` oscillates between `640x360` and `320x180` **every single frame**, causing `eng_surface_get` (`rsx_draw_engine.c:795`) to destroy and reallocate the Metal render-target texture twice every frame (due to pitch mismatch `2560 != 1280`). Keying surfaces by `(location, offset, w, h)` or avoiding destruction when a smaller mip/pass aliases the same VRAM offset will eliminate that thrash.
   - **Profile 3D gameplay** with `sample <pid> 2` while in playable 3D Sarif Industries (before any freeze) and inspect `RSX_ENGINE_PASS_DUMP` during gameplay to verify whether any UI/HUD passes are missing or slow, and check why gameplay drops below 30 fps.
   - **Look up and register unresolved NID `0x26090058`** (`sysPrxForUser`, printed once in `run_playtest.log`).
3. **60 fps investigation:** DX:HR targets 30 fps on PS3 (`cellGcmSetFlipMode(2)` / game internal frame cap). Check if `cellGcmSetFlipMode` or a game-side VBlank/wait count (`SemWVBL`) locks it to 30 fps once 3D frame time is under 16 ms.
4. **Upstream PRs to `sp00nznet/ps3recomp` & public GitHub repo (reproducible from user's own ISO):**
   - **Strong upstream PR candidates from this port:**
     1. `CellSpursQueue` official 128-byte BE struct layout fix (`+0x08 size`, `+0x0C depth`, `+0x10 u64 buffer`, `+0x18 eventPort`, `+0x1C direction`) + 4-arg `cellSpursQueuePopBody(q, buf, isPeek, isBlocking)` (`libs/spurs/cellSpurs.c`).
     2. `spu_dma.h` per-job `t_rep` repeat-transfer watchdog reset (prevents false-positive `spu_halt` after 256+ frames on single-PUT completion jobs).
     3. `spurs_job.c` SPU `$sp` word-1 stack-budget initialization (`ctx.gpr[1]._u32[1]`).
     4. `cellSpursShutdownJobChain` / `JoinJobChain` `shutdown_req` race fix + ring job-chain self-`NEXT` condvar parking.
     5. `rsx_draw_engine.c` `CELL_GCM_SURFACE_TARGET_NONE` guard in `eng_current_target_set` (prevents 1×1 surface clobber of display buffer 0).
     6. `cellGcmSys.c` `cellGcmSetQueueHandler` dispatch on flip (`gcm_note_queue_flip`) + rate-limiting `AddressToOffset REFUSED`.
     7. `cellGame.c` `cellGameDeleteGameData` guest-pointer translation fix.
     8. `PS3RecompSPU.cmake` / `build_spu_workloads.py` / `spu_program_pipeline.py` `--return-entries` per-image support (for FMOD mixers).
   - **Public repo structure (like `erikomis/afro-samurai-recomp`):** Only commit build/extract/lift scripts, CMake project, toolkit patch, README, and credits — **never** commit ISO data, `work/EBOOT.elf`, `recompiled/`, `spu_imgs/`, `jobdump/`, or `port-afro/spu/` lifted game code.
   - **Credits to include:** `sp00nznet/ps3recomp` (core toolkit & runtime), `erikomis` (`afro-samurai-recomp` macOS/Metal/FMOD patches & scripts, `infamous2-recomp`), RPCS3 team (decryption & PS3 LLE/HLE documentation), Eidos Montréal / Nixxes / Square Enix (original game).
5. **Cleanup:** Remove old `.log` and `.ppm` files in the workspace root (`run_playtest.log` is 85 MB; `run_live.log` is 45 MB; disk is ~32 GB free).

## Session 2 (2026-11-18 evening) — findings (resolved in Session 3)

- **Current blocker: unpatched jump-park in the main FIFO.** Frame 2 holds a self-jump at IO `0x2AB0` (`0x20002AB0`) with real
  commands after it. Something in the game should overwrite it (likely with a CALL into a sub-buffer); nothing ever does
  (`GCM_PARK_GRACE_MS=600000` → never patched). With the default 50 ms grace the runtime resyncs get→put
  (`FIFO resync (jump-park) 0x2AB0 -> 0x54A0`), which **skips the flip markers at 0x389C and 0x549C** → only 1 guest flip ever
  → `SemWGPU` stops being posted → main thread blocks in `sys_semaphore_wait(sem=1 'SemWGPU')`.
  Next: find who writes `0x10002AB0` (candidates: Execute Flush Thread `func_0024D4EC`, an SPU job, the Display Frame Thread which
  is never kicked — see below). Cheap workaround to try: make the jump-park resync also replay flip markers it skips.
- Display Frame Thread (tid 16) / Update Mesh Contexts Thread (tid 8) use a 2-lwmutex handshake (worker: lock A=obj+0x10, unlock
  B=obj+0x30, `func_00186F48`; main kicks via vtable `0xf85a48` slot +8 `func_001870B4`: unlock A, lock B). Main never kicks them
  in the first 3 frames. Trace with `PS3_LWM_WATCH=0x11320000,0x11320020,0x1121B210,0x1121B230` (new, ppu_sysprx.cpp).
- `SemWGPU` (sem 1, init 2) is posted by the game's queue handler (`cellGcmSetQueueHandler`, opd 0xFDB8E8). The toolkit stored it but
  never called it. **Fixed** in `libs/video/cellGcmSys.c` (`gcm_note_queue_flip`): one call per flip, arg 1, as RPCS3 does
  (`rsx_methods.cpp flip_command`).
- **FMOD mixer re-lifted with Afro's `--return-entries --merge-chunks`** (in place, in `port-afro/build/generated_spu/spu_64b58525…`;
  backup of the old lift in the session scratchpad, gone after reboot). Mixer job now runs continuously. **A cmake reconfigure
  regenerates generated_spu and loses this** — re-run the lifter command (spu_lifter.py … --base 12288 --return-entries --merge-chunks) or
  wire it into `PS3RecompSPU.cmake`.
- Intermittent (~1 in 3 runs) `Out of memory, "Misc" requested 0x7ffb60c bytes` early in boot → crash (exit 139). Race, not yet
  chased. `func_0036474C` debug hook now also prints a guest back-chain (`[DBG 36474C] frameN lr=`).
- New debug: `[heartbeat] guest flips=N` every 5 s (port-afro/main.cpp), `FLIP_DBG=1` now prints the context/IO each flip lands at.
  Headless frame dumps before the first guest flip are host "free presents" (black, `draws=0`), not game frames.
- `job[2]: implausible binary (ea=0 size=0) -- skipped` in the "ResolveDecompressor" job chain: command word `0x2` treated as a job.
  Probably a chain control command the runtime misreads; check if it matters.

## Where it was stuck before session 2 (kept for history)

- **No frame presented.** The headless frame dump produces nothing even after 60 s. The last sampled state (`sample <pid>`): several threads are in
  `sys_cond_wait` or `sys_lwmutex_lock`, two threads ping-pong one lwmutex (`LWM-BLOCK/LWM-GOT` tids 12/13), and SPU-lifted functions of image 0
  (158 KB, the EDGE/inflate-style task) appear in PPU call chains and block on a cond var. Start by finding what each game thread waits on
  (`sample`, `SEMTID=1`, `HLE_BT_EVERY`), and why no flip/`cellGcmSetFlip` is ever issued.
- **Apply Afro's mixer flags.** Afro lifts the FMOD mixer (our SPU image 1) with `--return-entries --merge-chunks`
  (`ref/afro_lift_spu.sh`). I did **not** apply that; the auto-generated lift uses defaults. Their note says without it a plugin return
  lands in the middle of a mixer function and the mixer job ends, freezing the game on FMOD's flags. High-probability suspect.
- **Unresolved imports** (return garbage in r3): `sys_net` `listen/accept/send/inet_addr`, `cellSpursQueuePopBody` (the toolkit's
  `QueuePushBody` is itself an experimental stub), `sys_io` `cellKbRead`. Network ones are probably harmless; queue pop may not be.
- One raw job binary can still go missing in later game phases; use the dump loop above.
- The lifted 19,776-byte job had 11 unsupported SPU instructions (falls back to the interpreter).
- Unmerged upstream PRs that may matter for a flip stall: #741 (opt-in Metal present thread), #721, #724 (flip pacing). #808 and #797 are already in the stock tree only, **not** in `ps3recomp-afro`.

## Gotchas

- `recompiled/ppu_recomp_008.cpp` contains a **temporary debug `fprintf`** at the top of `func_0036474C` (the game's "Out of memory"/error logger). The original is at `/tmp/ppu_recomp_008.cpp.orig` (may be gone). Re-lifting removes it.
- Lifted `b .` (branch to self, e.g. the game's deliberate hang in `func_0013E42C`) becomes an empty infinite loop, which clang treats as undefined behavior → segfault at pc 0. If you see exit 139 right after a game fatal error, look for the game's own error message first.
- `ps3recomp-afro` is a worktree with 48 uncommitted files (the Afro patch plus my edits); the stock `ps3recomp` is on branch `dxhr-local`. Don't mix their build dirs.
- The game ignores SIGTERM. `pkill -9 -x MyGameRecomp` between runs.
- Builds: ~15 min cold (29 PPU chunks, 3–4 GB RAM each at the high end); incremental link-only builds are about 30 s. Disk was at ~45 GB free; the game is 7.9 GB and `recompiled/` 1.4 GB.
- `screencapture` did not work from the agent shell, so the window was never viewed directly; "black" comes from the user's report plus the empty frame dump.

## Notes

- The disc key file (`.dkey`) was never needed. The ISO's sectors are plain despite the 3k3y header.
- The project note for future Claude sessions is `~/.claude/projects/-Users-matbook2/memory/project_dxhr_ps3recomp.md`.
- Upstream activity feed for PS3 recomp projects: github.com/undecuple/ps3rc-feed. Active macOS porters: erikomis, n0madic (Resistance 3).
