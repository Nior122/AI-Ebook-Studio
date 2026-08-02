// ESLint flat config for the AI Ebook Studio frontend.
// Uses FlatCompat to inherit the battle-tested "next/core-web-vitals" and
// "next/typescript" rule sets that ship with eslint-config-next.
// @eslint/eslintrc ships as a transitive dependency of eslint v9.
import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const compat = new FlatCompat({ baseDirectory: __dirname });

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    // The codebase aims for a high type-safety baseline.
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/consistent-type-imports": "warn",
      "react/no-unescaped-entities": "off",
    },
  },
];

export default eslintConfig;
