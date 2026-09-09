// glue.cpp - WebAssembly rozhrani jadra vAmiga.
// Prevzato 2026-09-06 z projektu Turrican (../Turrican-projekt, M4); jadro
// je herne agnosticke, SWIV si sem bude pridavat vlastni exporty.
//
// Zadne vlakno: JS (worker) vola wasm_step() 50x za sekundu, jadro spocita
// jeden PAL snimek (Emulator::stepFrame, patch tools/vamiga-wasm.patch).
// Stav hry se cte primo z chip RAM v haldе wasm (wasm_chip_ptr), obraz z
// textury (wasm_texture_ptr, vyrez jako VAHeadless: radky 26..310, sloupce
// 124..839), zvuk pres copyStereo, vstup pres GamePadAction / KeyCode,
// libovolny prikaz RetroShellu pres wasm_retroshell (stejne skripty jako
// v headless, vcetne 'w.w' patchu a 'amiga set').
#include "config.h"
#include "debug.h"
#include "VAmiga.h"
#include "Emulator.h"
#include "Memory.h"
#include "Agnus.h"
#include "AudioPort.h"
#include <emscripten.h>
#include <cstring>
#include <string>

using namespace vamiga;

static VAmiga *va = nullptr;
static long frames = 0;
static std::string lastError;
static float audioL[4096], audioR[4096];


extern "C" {

EMSCRIPTEN_KEEPALIVE int wasm_init()
{
    try {
        if (!va) {
            va = new VAmiga();
            // bez emulacniho vlakna: inicializace komponent, kterou jinak dela
            // Thread::runLoop (RetroShell, vychozi konfigurace, latch)
            va->emu->initialize();
            va->emu->markLaunched();
        }
        // Konfigurace jako VAHeadless `regression setup A500_OCS_1MB` (schema
        // resetuje volby, proto az po nem vlastni nastaveni).
        va->set(ConfigScheme::A500_OCS_1MB);
        va->set(Opt::AMIGA_VIDEO_FORMAT, (i64)TV::PAL);
        // Paleta COLOR (jas 50, kontrast 100, sytost 50, gamma), ne RGB:
        // `regression setup` v RetroShellu vola prepare() (nastavi RGB) a hned
        // potom emulator.set(scheme), ktery vraci vychozi konfiguraci
        // (CommanderConsole.cpp, PixelEngine::updateAdjLut). Zmereno dumpem
        // `monitor` v VAHeadless: PALETTE COLOR; s RGB je obraz linearni
        // (208 misto 196) a shoda s referencemi jen 48 %.
        va->set(Opt::MON_PALETTE, (i64)Palette::COLOR);
        va->set(Opt::DENISE_FRAME_SKIPPING, 0);   // i ve warpu prehazovat buffery kazdy snimek (Denise::vsyncHandler)
        va->set(Opt::AUD_ASR, 0);          // bez adaptivni vzorkovaci frekvence: pevne HOST_SAMPLE_RATE * 568408 / 28375160 vzorku na snimek
        va->set(Opt::AUD_PAN0, 50); va->set(Opt::AUD_PAN1, 50);
        va->set(Opt::AUD_PAN2, 50); va->set(Opt::AUD_PAN3, 50);
        return 0;
    } catch (std::exception &e) { lastError = e.what(); return -1; }
}

EMSCRIPTEN_KEEPALIVE const char *wasm_error() { return lastError.c_str(); }

// RetroShell prikaz(y) - vykonaji se pri dalsim wasm_update/wasm_step.
EMSCRIPTEN_KEEPALIVE int wasm_retroshell(const char *script)
{
    try { va->retroShell.execScript(std::string(script)); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

// Zpracuje frontu prikazu bez pocitani snimku (konfigurace pred zapnutim).
EMSCRIPTEN_KEEPALIVE int wasm_update()
{
    try { va->emu->stepFrameCommandsOnly(); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

EMSCRIPTEN_KEEPALIVE int wasm_load_rom(const u8 *buf, int len)
{
    try { va->mem.loadRom(buf, len); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

EMSCRIPTEN_KEEPALIVE int wasm_insert_disk(int drive, const u8 *buf, int len)
{
    try {
        std::span<const u8> sp(buf, (size_t)len);
        if (drive == 0) va->df0.insert(sp, ImageFormat::ADF, false);
        else va->df1.insert(sp, ImageFormat::ADF, false);
        return 0;
    } catch (std::exception &e) { lastError = e.what(); return -1; }
}

EMSCRIPTEN_KEEPALIVE int wasm_eject_disk(int drive)
{
    try { (drive == 0 ? va->df0 : va->df1).ejectDisk(); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

EMSCRIPTEN_KEEPALIVE int wasm_power_on()
{
    try {
        if (!va->isPoweredOn()) va->powerOn();
        if (!va->isRunning()) va->run();
        return 0;
    } catch (std::exception &e) { lastError = e.what(); return -1; }
}

EMSCRIPTEN_KEEPALIVE int wasm_is_running() { return va && va->isRunning(); }

// Jeden PAL snimek. Vraci cislo snimku od zapnuti, -1 pri chybe, -2 kdyz se
// jadro samo zastavilo (breakpoint apod.).
// Emuluje od hranice snimku (vcetne prikazu RetroShellu) az do zacatku rastroveho
// radku `line` - vzorkovani RAM v okamziku copper preruseni hry (radek 235).
// Zbytek snimku dokonci wasm_step().
static bool midFrame = false;
EMSCRIPTEN_KEEPALIVE int wasm_step_line(int line)
{
    try { if (!midFrame) { va->emu->stepToLine(line); midFrame = true; } return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

EMSCRIPTEN_KEEPALIVE long wasm_step()
{
    try {
        if (midFrame) { va->emu->stepFrameRest(); midFrame = false; } else va->emu->stepFrame();
        frames++;
        Message msg;
        while (va->msgQueue.getMsg(msg)) { /* bez posluchace: vyprazdnit frontu */ }
        return frames;
    } catch (std::exception &e) { lastError = e.what(); return -1; }
    catch (...) { return -2; }
}

EMSCRIPTEN_KEEPALIVE long wasm_frames() { return frames; }
// Text konzole RetroShellu (vystup prikazu, napr. dump konfigurace).
EMSCRIPTEN_KEEPALIVE const char *wasm_retroshell_text() { return va->retroShell.text(); }
// Citac snimku Agnusu (pos.frame) - kontrola, ze jeden krok = jeden snimek.
EMSCRIPTEN_KEEPALIVE long wasm_agnus_frame() { return (long)va->agnus.agnus->pos.frame; }

EMSCRIPTEN_KEEPALIVE const u8 *wasm_chip_ptr() { return va->mem.mem->chip; }
EMSCRIPTEN_KEEPALIVE long wasm_chip_size() { return (long)va->mem.getConfig().chipSize; }
EMSCRIPTEN_KEEPALIVE const u8 *wasm_slow_ptr() { return va->mem.mem->slow; }
EMSCRIPTEN_KEEPALIVE long wasm_slow_size() { return (long)va->mem.getConfig().slowSize; }

// Textura 912 x 313 x u32 (RGBA, R v nejnizsim bajtu).
EMSCRIPTEN_KEEPALIVE const u32 *wasm_texture_ptr() { return va->videoPort.getTexture(); }
EMSCRIPTEN_KEEPALIVE int wasm_texture_width() { return (int)HPIXELS; }
EMSCRIPTEN_KEEPALIVE int wasm_texture_height() { return (int)VPIXELS; }

// Zvuk: zkopiruje az n vzorku (stereo, float -1..1) do internich bufferu.
// Pocet vzorku pripravenych ve streamu jadra (AudioPort::stream). Worker si
// bere jen tolik, kolik je: copyStereo s vetsim n hlasi underflow, maze buffer
// a pres detektor vzorkovaci frekvence rozhazi produkci (mereno: 2931 vzorku
// na snimek misto 883 pri n = 4096).
EMSCRIPTEN_KEEPALIVE int wasm_audio_count() { return (int)va->audioPort.port->stream.count(); }
EMSCRIPTEN_KEEPALIVE int wasm_audio_copy(int n)
{
    if (n > 4096) n = 4096;
    return (int)va->audioPort.copyStereo(audioL, audioR, n);
}
EMSCRIPTEN_KEEPALIVE const float *wasm_audio_left() { return audioL; }
EMSCRIPTEN_KEEPALIVE const float *wasm_audio_right() { return audioR; }
EMSCRIPTEN_KEEPALIVE int wasm_set_sample_rate(int rate)
{
    try { va->set(Opt::HOST_SAMPLE_RATE, (i64)rate); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

// Joystick / mys: port 1 nebo 2, action = GamePadAction (0 PULL_UP, 1 PULL_DOWN,
// 2 PULL_LEFT, 3 PULL_RIGHT, 4 PRESS_FIRE, 7 PRESS_LEFT (mys), 10 RELEASE_X,
// 11 RELEASE_Y, 12 RELEASE_XY, 13 RELEASE_FIRE, ...).
EMSCRIPTEN_KEEPALIVE int wasm_joystick(int port, int action)
{
    try { (port == 1 ? va->controlPort1 : va->controlPort2).joystick.trigger((GamePadAction)action); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}
EMSCRIPTEN_KEEPALIVE int wasm_mouse(int port, int action)
{
    try { (port == 1 ? va->controlPort1 : va->controlPort2).mouse.trigger((GamePadAction)action); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

// Klavesnice: surovy kod Amigy (0x40 mezernik, 0x50 F1, ...), down = 1/0.
EMSCRIPTEN_KEEPALIVE int wasm_key(int code, int down)
{
    try { if (down) va->keyboard.press((KeyCode)code); else va->keyboard.release((KeyCode)code); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

// --- SWIV: zaznam zapisu do custom registru (patch tools/vamiga-regtrace) ---
// Cilem je zjistit, KDO kresli: herni kod na blitter/copper/bitplany vubec
// nesaha (0 z 14/6/26 registru), takze musi jit o kod, ktery jsme jeste
// nenasli. Kazdy zaznam nese registr, hodnotu, PC instrukce, priznak
// Agnus/CPU a rastrovou pozici.
EMSCRIPTEN_KEEPALIVE int wasm_regtrace(int on)
{
    vamiga::regTraceOn = on != 0;
    if (on) vamiga::regTraceCount = 0;
    return 0;
}
EMSCRIPTEN_KEEPALIVE int wasm_regtrace_count()
{
    return (int)vamiga::regTraceCount;
}
EMSCRIPTEN_KEEPALIVE const void *wasm_regtrace_ptr()
{
    return (const void *)vamiga::regTrace;
}
EMSCRIPTEN_KEEPALIVE int wasm_regtrace_entry_size()
{
    return (int)sizeof(vamiga::RegTraceEntry);
}

EMSCRIPTEN_KEEPALIVE int wasm_warp(int on)
{
    try { if (on) va->warpOn(1); else va->warpOff(1); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

// Ulozeni/nacteni stavu: snapshot vAmigy (Media/Snapshot.h, bez komprese).
// wasm_snapshot_take vrati ukazatel na data (delka wasm_snapshot_size), platny
// do dalsiho volani; wasm_snapshot_load obnovi stav z bufferu (stejny format
// jako soubor .vamiga z GUI).
static std::unique_ptr<Snapshot> snap;
EMSCRIPTEN_KEEPALIVE const u8 *wasm_snapshot_take()
{
    try { snap = va->amiga.takeSnapshot(Compressor::NONE); return snap ? snap->data.ptr : nullptr; }
    catch (std::exception &e) { lastError = e.what(); return nullptr; }
}
EMSCRIPTEN_KEEPALIVE long wasm_snapshot_size() { return snap ? (long)snap->data.size : 0; }
EMSCRIPTEN_KEEPALIVE int wasm_snapshot_load(const u8 *buf, long len)
{
    try { Snapshot s(buf, (isize)len); va->amiga.loadSnapshot(s); return 0; }
    catch (std::exception &e) { lastError = e.what(); return -1; }
}

EMSCRIPTEN_KEEPALIVE const char *wasm_version()
{
    static std::string v = std::to_string(VER_MAJOR) + "." + std::to_string(VER_MINOR) + "." + std::to_string(VER_SUBMINOR) + (VER_BETA ? "b" + std::to_string(VER_BETA) : "");
    return v.c_str();
}

}
