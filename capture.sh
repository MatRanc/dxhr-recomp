#!/bin/zsh
# usage: ./capture.sh   -- while ./run.sh diag is running and the scene is on screen:
# grabs one frame's render passes (with shaders + per-draw constants) and a 5 s CPU profile.
cd ${0:A:h}
pid=$(pgrep -x MyGameRecomp) || { echo "game not running"; exit 1; }
touch capture
sample $pid 5 -file sample_capture.txt >/dev/null 2>&1
echo "captured: passdump/ and sample_capture.txt"
