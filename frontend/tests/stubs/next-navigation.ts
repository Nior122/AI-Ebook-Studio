// Stub for `next/navigation` used in the Vitest (jsdom) environment.
// The real Next.js module requires the App Router runtime; this provides the
// hooks our components use so they can be tested in isolation. The router
// returns a single shared spy object so tests can assert navigation calls.

const router = {
  replace: vi.fn(),
  push: vi.fn(),
  back: vi.fn(),
  forward: vi.fn(),
  refresh: vi.fn(),
  prefetch: vi.fn(),
};

export function useRouter() {
  return router;
}

export function useSearchParams() {
  return new URLSearchParams();
}

export function usePathname() {
  return "/";
}

export function useParams() {
  return {};
}

export function redirect() {
  return null;
}
