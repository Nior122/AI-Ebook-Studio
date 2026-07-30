// useMounted — returns `true` only after the component has hydrated on the client.
// Useful for guarding SSR-unsafe rendering and avoiding flash-of-incorrect-state.
// Tiny utility, but centralizing it prevents the same useEffect pattern being
// re-implemented across components (DRY).

import { useEffect, useState } from "react";

export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}
