/**
 * Placement Resolver — maps placement tags to DOM insertion.
 * Replaces the entire bdLayout cursor system with CSS flow.
 *
 * The browser handles all sizing, wrapping, and overflow automatically.
 * No height estimation. No cursor tracking. No collision detection.
 */

import { board, endRow, getElement, registerElement } from './state.js';

/**
 * Place an element into the board DOM based on its placement tag.
 * @param {HTMLElement} element - The element to place
 * @param {string} placement - Placement tag ('below', 'center', 'row-start', etc.)
 * @param {Object} cmd - Original command (for id registration)
 */
export function placeElement(element, placement, cmd) {
  const scene = board.liveScene;
  if (!scene) return;

  placement = placement || 'below';

  // Register element for {ref:id} and beside:/below: lookups
  if (cmd.id) {
    registerElement(cmd.id, element);
  }

  // ── DEFAULT: below (normal block flow) ──
  if (placement === 'below') {
    endCurrentRowIfNeeded(placement);
    scene.appendChild(element);
    return;
  }

  // ── CENTER ──
  if (placement === 'center') {
    endCurrentRowIfNeeded(placement);
    element.classList.add('bd-placement-center');
    scene.appendChild(element);
    return;
  }

  // ── RIGHT ──
  if (placement === 'right') {
    endCurrentRowIfNeeded(placement);
    element.classList.add('bd-placement-right');
    scene.appendChild(element);
    return;
  }

  // ── INDENT ──
  if (placement === 'indent') {
    endCurrentRowIfNeeded(placement);
    element.classList.add('bd-placement-indent');
    scene.appendChild(element);
    return;
  }

  // ── FULL-WIDTH ──
  if (placement === 'full-width') {
    endCurrentRowIfNeeded(placement);
    scene.appendChild(element);
    return;
  }

  // ── ROW-START ──
  if (placement === 'row-start') {
    endCurrentRowIfNeeded(placement);
    const row = document.createElement('div');
    row.className = 'bd-row';
    row.appendChild(element);
    scene.appendChild(row);
    board.currentRow = row;
    return;
  }

  // ── ROW-NEXT ──
  if (placement === 'row-next') {
    if (!board.currentRow) {
      // No active row — start one implicitly
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

  // ── BESIDE:ID ──
  if (placement.startsWith('beside:')) {
    const refId = placement.split(':')[1];
    const refEl = getElement(refId);
    if (refEl) {
      // If ref is already in a row, append to that row
      const parentRow = refEl.closest('.bd-row');
      if (parentRow) {
        parentRow.appendChild(element);
        board.currentRow = parentRow;
      } else {
        // Wrap ref and new element in a row
        const row = document.createElement('div');
        row.className = 'bd-row';
        refEl.parentNode.insertBefore(row, refEl);
        row.appendChild(refEl);
        row.appendChild(element);
        board.currentRow = row;
      }
    } else {
      // Ref not found — fallback to below
      endCurrentRowIfNeeded(placement);
      scene.appendChild(element);
    }
    return;
  }

  // ── BELOW:ID ──
  if (placement.startsWith('below:')) {
    const refId = placement.split(':')[1];
    const refEl = getElement(refId);
    if (refEl) {
      // Insert after the ref element (or after its parent row)
      const insertAfter = refEl.closest('.bd-row') || refEl;
      if (insertAfter.nextSibling) {
        insertAfter.parentNode.insertBefore(element, insertAfter.nextSibling);
      } else {
        insertAfter.parentNode.appendChild(element);
      }
    } else {
      // Ref not found — fallback to below
      scene.appendChild(element);
    }
    return;
  }

  // ── UNKNOWN — fallback to below ──
  endCurrentRowIfNeeded(placement);
  scene.appendChild(element);
}

/**
 * End the current row if the new placement type requires it.
 * Row-start and row-next maintain rows; everything else closes them.
 */
function endCurrentRowIfNeeded(placement) {
  if (placement !== 'row-start' && placement !== 'row-next') {
    endRow();
  }
}
