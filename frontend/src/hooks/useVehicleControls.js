import { useCallback, useMemo, useState } from "react";

/**
 * Centralizes pedal/indicator/horn input handling so every view (top-down
 * dashboard, driver's view) shares one source of truth for "is this
 * control currently pressed" -- driving animations (brake glow, headlight
 * beams, blinker timing) needs that instant local state, since waiting on
 * a car_state round trip through the backend would make every animation
 * lag a network hop behind the actual button press.
 */
export function useVehicleControls(sendControl) {
  const [pressed, setPressed] = useState({
    throttle: false,
    brake: false,
    left: false,
    right: false,
    horn: false,
  });

  const bind = useCallback(
    (key, signal, downValue, upValue) => {
      const down = (e) => {
        e?.preventDefault?.();
        setPressed((p) => (p[key] ? p : { ...p, [key]: true }));
        sendControl(signal, { value: downValue });
      };
      const up = (e) => {
        e?.preventDefault?.();
        setPressed((p) => (p[key] ? { ...p, [key]: false } : p));
        sendControl(signal, { value: upValue });
      };
      return {
        onMouseDown: down,
        onMouseUp: up,
        onMouseLeave: up,
        onTouchStart: down,
        onTouchEnd: up,
      };
    },
    [sendControl]
  );

  const handlers = useMemo(
    () => ({
      accelerate: bind("throttle", "throttle", 1, 0),
      brake: bind("brake", "throttle", -1, 0),
      left: bind("left", "turning", -1, 0),
      right: bind("right", "turning", 1, 0),
      horn: bind("horn", "horn", 1, 0),
    }),
    [bind]
  );

  return { pressed, handlers };
}
