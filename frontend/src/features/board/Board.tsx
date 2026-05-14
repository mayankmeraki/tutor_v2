import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
} from 'react';
import { Board as Engine, type BoardCommand } from './engine';
import { snapshotScene } from './engine/scene';
import './board.css';

export interface BoardHandle {
  queue: (cmd: BoardCommand) => void;
  cancel: () => void;
  resume: () => void;
  setReplayMode: (on: boolean) => void;
  snapshotScene: () => void;
  clearAll: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
  zoomReset: () => void;
  zoomPulse: (id: string) => void;
  scrollToElement: (id: string) => void;
}

interface BoardProps {
  className?: string;
  apiUrl?: string;
  onReady?: () => void;
}

export const Board = forwardRef<BoardHandle, BoardProps>(function Board(
  { className, apiUrl, onReady },
  ref,
) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const stackRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!wrapRef.current || !contentRef.current || !stackRef.current) return;
    Engine.init({
      apiUrl,
      rootEl: wrapRef.current,
      contentEl: contentRef.current,
      scenesStackEl: stackRef.current,
      wrapEl: wrapRef.current,
    });
    onReady?.();
    return () => Engine.destroy();
  }, [apiUrl, onReady]);

  useImperativeHandle(
    ref,
    () => ({
      queue: (cmd: BoardCommand) => Engine.queueCommand(cmd),
      cancel: () => Engine.cancel(),
      resume: () => Engine.resume(),
      setReplayMode: (on: boolean) => Engine.setReplayMode(on),
      snapshotScene: () => snapshotScene(),
      clearAll: () => Engine.clearAll(),
      zoomIn: () => Engine.zoomIn(),
      zoomOut: () => Engine.zoomOut(),
      zoomReset: () => Engine.zoomReset(),
      zoomPulse: (id: string) => Engine.zoomPulse(id),
      scrollToElement: (id: string) => Engine.scrollToElement(id),
    }),
    [],
  );

  return (
    <div
      ref={wrapRef}
      id="bd-canvas-wrap"
      className={`bd-canvas-wrap ${className ?? ''}`}
    >
      <div ref={contentRef} id="bd-board-content" className="bd-board-content">
        <div ref={stackRef} id="bd-scenes-stack" className="bd-scenes-stack" />
      </div>
      <div className="bd-zoom-controls">
        <button type="button" onClick={() => Engine.zoomOut()} title="Zoom out">
          −
        </button>
        <button type="button" onClick={() => Engine.zoomReset()} title="Reset">
          ◯
        </button>
        <button type="button" onClick={() => Engine.zoomIn()} title="Zoom in">
          +
        </button>
      </div>
    </div>
  );
});
