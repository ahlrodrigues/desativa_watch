from __future__ import annotations

from typing import Iterator, List, Sequence, Tuple

from selenium.webdriver.common.by import By

FramePath = Tuple[int, ...]


def switch_to_frame_path(driver, path: Sequence[int]) -> None:
    """Troca para um caminho de iframes a partir do topo."""
    driver.switch_to.default_content()
    for idx in path:
        driver.switch_to.frame(idx)


def iter_frame_paths(driver, max_depth: int = 4) -> Iterator[FramePath]:
    """
    Gera todos os caminhos de iframe acessíveis, incluindo o topo: ().
    O estado original é restaurado ao final.
    """
    original_path = current_frame_path(driver, max_depth=max_depth)
    try:
        yield ()
        yield from _iter_children(driver, (), depth=0, max_depth=max_depth)
    finally:
        switch_to_frame_path(driver, original_path)


def current_frame_path(driver, max_depth: int = 4) -> FramePath:
    """
    Tenta inferir o caminho do iframe atual. Se falhar, assume topo.
    """
    try:
        path: List[int] = driver.execute_script(
            """
            const out = [];
            let w = window;
            let guard = 0;
            while (w !== w.top && guard++ < 20) {
              const parent = w.parent;
              let idx = -1;
              for (let i = 0; i < parent.frames.length; i++) {
                if (parent.frames[i] === w) { idx = i; break; }
              }
              if (idx < 0) return [];
              out.unshift(idx);
              w = parent;
            }
            return out;
            """
        ) or []
        return tuple(int(x) for x in path[:max_depth])
    except Exception:
        return ()


def _iter_children(driver, base_path: FramePath, depth: int, max_depth: int) -> Iterator[FramePath]:
    if depth >= max_depth:
        return

    try:
        switch_to_frame_path(driver, base_path)
        frames = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        return

    for idx in range(len(frames)):
        child_path = tuple(base_path) + (idx,)
        yield child_path
        yield from _iter_children(driver, child_path, depth + 1, max_depth)
