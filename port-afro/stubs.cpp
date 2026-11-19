/*
 * ps3recomp game project -- game-specific hooks and overrides.
 *
 * main.cpp is the runner and is game-agnostic. This file is where a port puts
 * everything that is not: the PRX loading hook it must answer, overrides for
 * firmware functions the HLE library gets wrong for this title, and patches
 * over recompiled code.
 *
 * It starts out as the empty version of all of that, which is what a game with
 * no lifted PRX and no overrides needs.
 */

#include <cstdint>
#include <cstdio>
#include <cstring>

#include "ps3emu/ps3types.h"
#include "ps3emu/error_codes.h"

extern "C" {
    void ps3_hle_register(uint32_t nid, const char* name, void* handler);
    void cellKbRead(void);
    void cellSpursQueuePopBody(void);
    void sys_net_bnet_listen(void);
    void sys_net_bnet_accept(void);
    void sys_net_bnet_send(void);
    void sys_net_bnet_inet_addr(void);
}

/* ---------------------------------------------------------------------------
 * PRX loading & DXHR NID registrations
 *
 * main.cpp calls this once, after the lifted function table is registered and
 * vm_base is live, before the game runs. A title that lifts a real system PRX
 * -- libsre, which is cellSpurs and cellSync -- loads its image into guest RAM
 * here and registers its exports. Most ports never need to: the HLE library
 * answers those modules instead.
 * -----------------------------------------------------------------------*/

extern "C" void ps3_load_prx_modules(void)
{
    /* Register NIDs missing from stock gen_hle_nids.py output so a freshly
     * regenerated recompiled/ppu_hle_nids.cpp works without manual edits. */
    ps3_hle_register(0xFF0A21B7u, "cellKbRead", (void*)cellKbRead);
    ps3_hle_register(0x91066667u, "cellSpursQueuePopBody", (void*)cellSpursQueuePopBody);
    ps3_hle_register(0x28E208BBu, "listen", (void*)sys_net_bnet_listen);
    ps3_hle_register(0xC94F6939u, "accept", (void*)sys_net_bnet_accept);
    ps3_hle_register(0xDC751B40u, "send", (void*)sys_net_bnet_send);
    ps3_hle_register(0xDABBC2C0u, "inet_addr", (void*)sys_net_bnet_inet_addr);
}

/* ---------------------------------------------------------------------------
 * Example: Override a specific NID
 *
 * The module system resolves function imports by NID.  To replace a default
 * HLE stub with custom logic, register your function at init time.
 * -----------------------------------------------------------------------*/

/*
 * Example: override cellGcmSetFlipMode (NID 0xA53D12AE) to force vsync.
 *
 *   static void my_cellGcmSetFlipMode(u32 mode)
 *   {
 *       printf("[hook] cellGcmSetFlipMode: forcing VSYNC (was %u)\n", mode);
 *       // Force vsync regardless of what the game requested
 *       cellGcmSetFlipMode(CELL_GCM_DISPLAY_VSYNC);
 *   }
 *
 * Then in your init code:
 *
 *   ps3::modules::override_nid(0xA53D12AE,
 *       reinterpret_cast<void*>(my_cellGcmSetFlipMode));
 */

/* ---------------------------------------------------------------------------
 * Example: Hook into module loading
 *
 * You can intercept cellSysmoduleLoadModule to perform custom actions
 * when a particular module is loaded.
 * -----------------------------------------------------------------------*/

/*
 *   static s32 my_loadmodule_hook(u16 id)
 *   {
 *       printf("[hook] Module 0x%04X loaded\n", id);
 *
 *       if (id == CELL_SYSMODULE_AUDIO) {
 *           // Perform custom audio backend initialization
 *           init_my_audio_backend();
 *       }
 *
 *       // Call the original implementation
 *       return cellSysmoduleLoadModule(id);
 *   }
 */

/* ---------------------------------------------------------------------------
 * Game-specific patches
 *
 * Sometimes you need to patch recompiled code at specific addresses.
 * Use the patch system to modify behavior without editing generated code.
 * -----------------------------------------------------------------------*/

/*
 *   // Skip an integrity check at guest address 0x00812FA0
 *   ps3::patches::nop_range(0x00812FA0, 0x00812FB0);
 *
 *   // Replace a function call with a direct return
 *   ps3::patches::force_return(0x009A1000, 0);  // return 0
 */
