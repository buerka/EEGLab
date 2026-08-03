/// <reference types="astro/client" />

declare module '*.toml' {
  const value: Record<string, unknown>;
  export default value;
}
