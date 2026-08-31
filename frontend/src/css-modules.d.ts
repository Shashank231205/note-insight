/**
 * CSS Modules typing.
 *
 * Note: `noUncheckedIndexedAccess` is deliberately off in tsconfig.json. CSS
 * Modules resolve to an index signature, so with that flag every `styles.foo`
 * becomes `string | undefined` and each class name needs a non-null assertion.
 * Per-file class-name codegen would preserve both, and is the right fix at a
 * larger scale; for this build the assertions would cost more clarity than the
 * flag buys. Every other strict flag remains on.
 */

declare module '*.module.css' {
  const classes: Record<string, string>;
  export default classes;
}
