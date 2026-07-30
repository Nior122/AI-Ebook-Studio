// Prettier config for the AI Ebook Studio frontend.
// Enforces a single, consistent formatting baseline. The Tailwind plugin
// sorts class names deterministically so diffs stay small.
/** @type {import("prettier").Config} */
const config = {
  semi: true,
  singleQuote: false,
  trailingComma: "all",
  printWidth: 100,
  tabWidth: 2,
  plugins: ["prettier-plugin-tailwindcss"],
};

export default config;
