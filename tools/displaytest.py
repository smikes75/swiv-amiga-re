#!/usr/bin/env python3
"""Display controls, persistence and simulated 120 Hz presentation.

Run from any directory: python3 tools/displaytest.py
The high-DPI cases approximate Windows display scaling; they do not measure
physical monitor latency. Screenshots are written only when requested.
"""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def load_game(page):
    page.goto((ROOT / "game.html").as_uri())
    page.set_input_files("#fpick", str(ROOT / "SWIVFIX.ADF"))
    page.wait_for_selector("#titlewrap", state="visible")
    page.evaluate("window.requestAnimationFrame = () => 0")
    page.keyboard.press("Space")
    page.wait_for_selector("#gamewrap", state="visible")
    page.evaluate("state.g.last = 1000; frame(1000)")


def geometry(page):
    return page.evaluate("""() => {
      const cv = document.querySelector('#game');
      const r = cv.getBoundingClientRect();
      const controls = document.querySelector('#testbar').getBoundingClientRect();
      return { width: parseFloat(cv.style.width), height: parseFloat(cv.style.height),
        fits: r.left >= 0 && r.right <= innerWidth + 1 &&
              controls.bottom <= innerHeight + 1,
        buffer: [cv.width, cv.height], tick: state.g.tick,
        scroll: state.g.scroll, label: document.querySelector('#zoomvalue').textContent };
    }""")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for dpr in [1, 1.25, 1.5, 2]:
                context = browser.new_context(viewport={"width": 1440, "height": 1000},
                                              device_scale_factor=dpr)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                load_game(page)
                initial = geometry(page)
                assert initial["width"] == 640 and initial["height"] == 512, initial
                for multiple in [1, 2, 3]:
                    page.click(f'[data-zoom="{multiple}"]')
                    size = geometry(page)
                    assert size["fits"] and size["width"] <= 320 * multiple, size
                    assert size["tick"] == initial["tick"], "zoom advanced game logic"
                    assert abs(size["width"] / size["height"] - 1.25) < .001, size
                page.locator("#zoomrange").evaluate("""el => {
                  el.value = '2.35'; el.dispatchEvent(new Event('input', {bubbles:true}));
                }""")
                size = geometry(page)
                assert size["width"] == 752 and size["label"] == "2,35×", size
                page.focus("#zoomrange")
                page.keyboard.press("ArrowRight")
                assert not page.evaluate("Boolean(state.g.keys.r)"), "slider moved helicopter"
                page.click('[data-zoom="2"]')
                page.check("#smoothchk")
                page.evaluate("frame(1000)")
                buffer = geometry(page)["buffer"]
                assert buffer == [1280, 1024], buffer
                for width, height in [(1920, 1080), (1280, 720), (800, 600), (390, 844)]:
                    page.set_viewport_size({"width": width, "height": height})
                    # Apply synchronously as resize is delivered on the next browser frame.
                    page.evaluate("applyGameZoom(); frame(1000)")
                    assert geometry(page)["fits"], geometry(page)
                    page.click("#zoomfit")
                    assert geometry(page)["fits"], geometry(page)
                    assert geometry(page)["buffer"] == buffer, "zoom changed interpolation precision"
                page.set_viewport_size({"width": 1440, "height": 1000})
                page.locator("#zoomrange").evaluate("""el => {
                  el.value = '2.35'; el.dispatchEvent(new Event('input', {bubbles:true}));
                }""")
                load_game(page)
                assert geometry(page)["width"] == 752, "fractional zoom was not restored"
                page.click('[data-zoom="2"]')
                assert page.get_attribute('[data-zoom="2"]', "aria-pressed") == "true"
                assert not errors, errors
                if dpr == 1 and os.environ.get("SWIV_DISPLAY_SCREENSHOT"):
                    page.evaluate("for (let i=0;i<160;i++) step(state.g); frame(1000)")
                    page.screenshot(path=os.environ["SWIV_DISPLAY_SCREENSHOT"])
                context.close()
                print(f"Zoom OK: DPR {dpr}, presets, slider, fit, keyboard, persistence", flush=True)

            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            load_game(page)
            result = page.evaluate("""() => {
              const snapshot = () => {
                const g = state.g;
                return { tick:g.tick, scroll:g.scroll, rng:g.rngState,
                  player:[g.player.x,g.player.y,g.player.alive], cost:g.activeCost,
                  air:g.air.map(a=>[a.kind,a.x,a.y,a.hp]),
                  shots:g.shots.map(s=>[s.kind,s.x,s.y]) };
              };
              const results = [];
              for (const zoom of [1,2.35,3]) {
                startGame(0); state.smooth = true; state.g.last = 1000;
                setGameZoom('manual',zoom);
                for (let i=1; i<=600; i++) frame(1000 + i*1000/120);
                const rendered = snapshot();
                startGame(0);
                for (let i=0; i<rendered.tick; i++) step(state.g);
                results.push({zoom, ticks:rendered.tick,
                  same:JSON.stringify(rendered)===JSON.stringify(snapshot())});
              }
              return results;
            }""")
            assert all(r["same"] and 249 <= r["ticks"] <= 250 for r in result), result
            print("120 Hz timing OK: identical simulation at 1×, 2.35× and 3×", flush=True)
            page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
