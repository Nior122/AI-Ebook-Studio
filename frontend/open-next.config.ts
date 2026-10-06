import { defineCloudflareConfig } from "@opennextjs/cloudflare/config";

const cloudflareConfig = defineCloudflareConfig();

export default {
  ...cloudflareConfig,
  // OpenNext otherwise runs `npm run build` for Next.js, which recursively
  // invokes this package's OpenNext build script.
  buildCommand: "npm run build:next",
};
