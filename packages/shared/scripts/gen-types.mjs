// Generates TypeScript types from the JSON schemas in ../schemas.
import { compileFromFile } from "json-schema-to-typescript";
import { readdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const schemaDir = path.join(root, "schemas");
const outDir = path.join(root, "types");
const banner = "/* Generated from packages/shared/schemas. Run `npm run gen:types` after editing a schema. */";

const files = (await readdir(schemaDir)).filter((f) => f.endsWith(".schema.json")).sort();
const exports = [];
for (const file of files) {
  const base = file.replace(".schema.json", "");
  const ts = await compileFromFile(path.join(schemaDir, file), {
    bannerComment: banner,
    cwd: schemaDir,
    additionalProperties: false,
  });
  await writeFile(path.join(outDir, `${base}.ts`), ts);
  exports.push(`export * from "./${base}";`);
}
await writeFile(path.join(outDir, "index.ts"), `${banner}\n${exports.join("\n")}\n`);
console.log(`Generated types for ${files.length} schemas.`);
