// PostCSS config — wires Tailwind CSS + autoprefixer into the Next.js build.
// Tailwind is the styling layer; autoprefixer adds vendor prefixes for browser compat.
/** @type {import('postcss-load-config').Config} */
const config = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};

export default config;
