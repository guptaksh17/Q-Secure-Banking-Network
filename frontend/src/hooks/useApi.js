import { useCallback, useEffect, useRef, useState } from "react";

/** Load data on mount (and when deps change). Ignores responses from stale calls. */
export function useLoad(loader, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const callId = useRef(0);

  const reload = useCallback(() => {
    const id = ++callId.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    loader()
      .then((data) => id === callId.current && setState({ data, error: null, loading: false }))
      .catch((error) => id === callId.current && setState({ data: null, error, loading: false }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    reload();
  }, [reload]);

  return { ...state, reload };
}

/** Run an action on demand (form submit, "Run" button). */
export function useAction(action) {
  const [state, setState] = useState({ data: null, error: null, running: false });
  const run = useCallback(
    async (...args) => {
      setState((s) => ({ ...s, running: true, error: null }));
      try {
        const data = await action(...args);
        setState({ data, error: null, running: false });
        return data;
      } catch (error) {
        setState((s) => ({ ...s, error, running: false }));
        return null;
      }
    },
    [action],
  );
  return { ...state, run };
}
