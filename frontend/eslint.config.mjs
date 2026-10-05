import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

/**
 * Flat ESLint config.
 *
 * Next 16 removed the `next lint` command, which is what previously supplied
 * the config implicitly -- there was no eslint config file in this repo at all,
 * so linting silently depended on that command. ESLint is now invoked directly
 * and the ruleset is explicit and checked in.
 */
export default [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "public/**",
      "*.tsbuildinfo",
    ],
  },
  ...coreWebVitals,
  ...typescript,
  {
    rules: {
      // Editor.js tools and the block payloads they emit are untyped by design
      // (the schema lives in the backend serializer), so `any` at those seams is
      // deliberate rather than an oversight.
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
];
