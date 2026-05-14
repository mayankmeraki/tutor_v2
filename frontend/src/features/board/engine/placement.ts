/**
 * Placement Resolver — maps placement tags to DOM insertion.
 * Native TypeScript port of frontend-legacy/board/placement.js.
 */

import { board, getElement, registerElement, endRow, type BoardCommand } from './state';

export function placeElement(
  element: HTMLElement,
  placement: string | undefined,
  cmd: BoardCommand,
): void {
  const scene = board.liveScene;
  if (!scene) return;

  const place = placement ?? 'below';

  if (cmd.id) registerElement(cmd.id, element);

  if (place.startsWith('figure:')) {
    const figId = place.slice('figure:'.length);
    const fig = document.getElementById(figId);
    if (fig?.classList.contains('bd-figure')) {
      const narrationCol = fig.querySelector<HTMLElement>('.bd-figure-narration');
      if (narrationCol) {
        narrationCol.appendChild(element);
        requestAnimationFrame(() => {
          narrationCol.scrollTop = narrationCol.scrollHeight;
        });
        return;
      }
    }
  }

  if (board.currentColumns && place === 'below') {
    board.currentColumns.appendChild(element);
    return;
  }

  if (place === 'below') {
    endCurrentRowIfNeeded(place);
    scene.appendChild(element);
    return;
  }

  if (place === 'center') {
    endCurrentRowIfNeeded(place);
    element.classList.add('bd-placement-center');
    scene.appendChild(element);
    return;
  }

  if (place === 'right') {
    endCurrentRowIfNeeded(place);
    element.classList.add('bd-placement-right');
    scene.appendChild(element);
    return;
  }

  if (place === 'indent') {
    endCurrentRowIfNeeded(place);
    element.classList.add('bd-placement-indent');
    scene.appendChild(element);
    return;
  }

  if (place === 'full-width') {
    endCurrentRowIfNeeded(place);
    scene.appendChild(element);
    return;
  }

  if (place === 'row-start') {
    endCurrentRowIfNeeded(place);
    const row = document.createElement('div');
    row.className = 'bd-row';
    row.appendChild(element);
    scene.appendChild(row);
    board.currentRow = row;
    return;
  }

  if (place === 'row-next') {
    if (!board.currentRow) {
      const row = document.createElement('div');
      row.className = 'bd-row';
      row.appendChild(element);
      scene.appendChild(row);
      board.currentRow = row;
    } else {
      board.currentRow.appendChild(element);
    }
    return;
  }

  if (place.startsWith('beside:')) {
    const refId = place.split(':')[1];
    const refEl = getElement(refId);
    if (refEl) {
      const parentRow = refEl.closest('.bd-row') as HTMLElement | null;
      if (parentRow) {
        parentRow.appendChild(element);
        board.currentRow = parentRow;
      } else {
        const row = document.createElement('div');
        row.className = 'bd-row';
        refEl.parentNode?.insertBefore(row, refEl);
        row.appendChild(refEl);
        row.appendChild(element);
        board.currentRow = row;
      }
    } else {
      endCurrentRowIfNeeded(place);
      scene.appendChild(element);
    }
    return;
  }

  if (place.startsWith('below:')) {
    const refId = place.split(':')[1];
    const refEl = getElement(refId);
    if (refEl) {
      const insertAfter = (refEl.closest('.bd-row') as HTMLElement | null) ?? refEl;
      if (insertAfter.nextSibling) {
        insertAfter.parentNode?.insertBefore(element, insertAfter.nextSibling);
      } else {
        insertAfter.parentNode?.appendChild(element);
      }
    } else {
      scene.appendChild(element);
    }
    return;
  }

  endCurrentRowIfNeeded(place);
  scene.appendChild(element);
}

function endCurrentRowIfNeeded(placement: string): void {
  if (placement !== 'row-start' && placement !== 'row-next') {
    endRow();
  }
}
