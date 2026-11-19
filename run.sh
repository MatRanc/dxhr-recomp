#!/bin/zsh
# usage: ./run.sh [seconds] [logfile]   -- runs the DX:HR port with the macOS settings found so far
cd ${0:A:h}
# ./run.sh diag [secs] [log]: same run, plus the on-demand capture ./capture.sh triggers
if [[ $1 == diag ]]; then shift; rm -f capture; mkdir -p passdump shaderdump
  export RSX_ENGINE_PASS_DUMP=$PWD/passdump RSX_ENGINE_PASS_DUMP_DRAWS=1 \
         RSX_ENGINE_PASS_DUMP_TRIGGER=$PWD/capture RSX_ENGINE_SHADER_DUMP=$PWD/shaderdump; fi
GCM_HANDLER_THREAD=1 PS3_VFS_ROOT=$PWD/game PS3_HDD0_ROOT=$PWD/hdd0 PS3_HDD1_ROOT=$PWD/hdd1 \
PS3_GAMEDATA_ROOT=$PWD PS3_BOOT_PATH=/dev_bdvd/PS3_GAME/USRDIR/EBOOT.BIN \
PS3_DEV_FLASH="$HOME/Library/Application Support/rpcs3/dev_flash" PS3RECOMP_MSL_CACHE=$PWD/cache/msl \
GCM_ENGINE_3D_SUBCH=1 SPURS_JC_JOBLIST_PAR=4 SPURS_JC_JOB_PAR=${SPURS_JC_JOB_PAR:-4} SPURS_JC_SYNC_KICK=${SPURS_JC_SYNC_KICK-Rendering,ShaderPatch} SPU_MFC_LOOKUP_CACHE=${SPU_MFC_LOOKUP_CACHE:-1} SPURS_JG_WAIT_FOREVER=1 PS3_TITLE="Deus Ex HR" \
PS3_VERBOSE=${PS3_VERBOSE:-0} PS3_OVERLAY_HUD=${PS3_OVERLAY_HUD:-1} PS3_OVERLAY_HUD_GRAPH=${PS3_OVERLAY_HUD_GRAPH:-1} \
PS3_MOUSE_CAPTURE=${PS3_MOUSE_CAPTURE:-0} PS3_MOUSE=${PS3_MOUSE:-0} \
SPU_DUMP_MISS=${SPU_DUMP_MISS:-$PWD/jobdump} \
exec timeout -s KILL ${1:-60} port-afro/build/DeusExHR work/EBOOT.elf > ${2:-run.log} 2>&1
