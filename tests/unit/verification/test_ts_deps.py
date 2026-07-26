"""Test del collector di dipendenze locali TS/JS
(`assist.verification.ts_deps.TsDependencyCollector`)."""

from assist.verification.ts_deps import TsDependencyCollector


def test_import_semplice_relativo_e_raccolto(tmp_path):
    target = tmp_path / "main.ts"
    target.write_text('import { greet } from "./helper";\n\ngreet();\n')

    helper = tmp_path / "helper.ts"
    helper.write_text("export function greet(): void {}\n")

    result = TsDependencyCollector().collect(str(target))

    assert result == {"helper.ts": helper.read_text(encoding="utf-8")}


def test_import_con_risalita_directory_e_raccolto_con_chiave_corretta(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    target = src_dir / "main.ts"
    target.write_text('import { util } from "../shared/util";\n')

    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    util = shared_dir / "util.ts"
    util.write_text("export const util = 1;\n")

    result = TsDependencyCollector().collect(str(target))

    assert result == {"../shared/util.ts": util.read_text(encoding="utf-8")}


def test_index_ts_viene_risolto(tmp_path):
    target = tmp_path / "main.ts"
    target.write_text('import { sub } from "./sub";\n')

    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    index_file = sub_dir / "index.ts"
    index_file.write_text("export const sub = 1;\n")

    result = TsDependencyCollector().collect(str(target))

    assert result == {"sub/index.ts": index_file.read_text(encoding="utf-8")}


def test_import_pacchetto_npm_e_ignorato(tmp_path):
    target = tmp_path / "main.ts"
    target.write_text(
        'import { describe } from "vitest";\n'
        'import React from "react";\n'
        'import { helper } from "./helper";\n'
    )

    helper = tmp_path / "helper.ts"
    helper.write_text("export const helper = 1;\n")

    result = TsDependencyCollector().collect(str(target))

    assert result == {"helper.ts": helper.read_text(encoding="utf-8")}


def test_ricorsione_a_importa_b_importa_c(tmp_path):
    a = tmp_path / "a.ts"
    a.write_text('import { b } from "./b";\n')

    b = tmp_path / "b.ts"
    b.write_text('import { c } from "./c";\n\nexport const b = c;\n')

    c = tmp_path / "c.ts"
    c.write_text("export const c = 1;\n")

    result = TsDependencyCollector().collect(str(a))

    assert set(result) == {"b.ts", "c.ts"}
    assert result["b.ts"] == b.read_text(encoding="utf-8")
    assert result["c.ts"] == c.read_text(encoding="utf-8")


def test_max_files_limit_e_rispettato(tmp_path):
    imports = "\n".join(f'import {{ v{i} }} from "./mod{i}";' for i in range(10))
    target = tmp_path / "main.ts"
    target.write_text(imports + "\n")

    for i in range(10):
        (tmp_path / f"mod{i}.ts").write_text(f"export const v{i} = {i};\n")

    result = TsDependencyCollector().collect(str(target), max_files=3)

    assert len(result) <= 3


def test_import_dinamico_e_raccolto(tmp_path):
    target = tmp_path / "main.ts"
    target.write_text(
        'export async function load() {\n'
        '  const mod = await import("./dynamic");\n'
        '  return mod;\n'
        '}\n'
    )

    dynamic = tmp_path / "dynamic.ts"
    dynamic.write_text("export const value = 1;\n")

    result = TsDependencyCollector().collect(str(target))

    assert result == {"dynamic.ts": dynamic.read_text(encoding="utf-8")}


def test_target_stesso_non_incluso(tmp_path):
    target = tmp_path / "main.ts"
    target.write_text('import { helper } from "./helper";\n')

    helper = tmp_path / "helper.ts"
    helper.write_text("export const helper = 1;\n")

    result = TsDependencyCollector().collect(str(target))

    assert "main.ts" not in result
