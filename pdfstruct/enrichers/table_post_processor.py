"""
pdfstruct/enrichers/table_post_processor.py

Post-procesador de tablas Markdown.
Versión mejorada y más efectiva (pero aún conservadora).

Objetivo: reparar tablas que PyMuPDF4LLM suele dejar malformadas,
especialmente tablas con años, columnas n/% y filas partidas.
"""

from __future__ import annotations
import re
from typing import List


class TablePostProcessor:
    """Repara bloques de tabla Markdown con heurísticas."""

    _TABLE_ROW_RE = re.compile(r"^\|.*\|$", re.MULTILINE)
    _YEAR_RE = re.compile(r"\b(20\d{2})\b")
    _NUMBER_CELL_RE = re.compile(r"^\*?(\d+(?:[.,]\d+)?)\*?$")

    def process(self, markdown: str) -> str:
        """
        Procesa el markdown completo buscando bloques de tabla y reparándolos.
        """
        # 1. Intentar reconstruir filas que fueron partidas por saltos de línea internos
        rebuilt = self._rebuild_broken_rows(markdown)

        lines = rebuilt.splitlines()
        output: List[str] = []
        buffer: List[str] = []
        in_table = False

        for line in lines:
            if self._is_table_line(line):
                buffer.append(line)
                in_table = True
            else:
                if in_table and buffer:
                    output.extend(self._repair_table_block(buffer))
                    buffer = []
                    in_table = False
                output.append(line)

        if buffer:
            output.extend(self._repair_table_block(buffer))

        return "\n".join(output)

    # ------------------------------------------------------------------
    # Detección
    # ------------------------------------------------------------------
    @staticmethod
    def _is_table_line(line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("|") and stripped.endswith("|")

    # ------------------------------------------------------------------
    # Reconstrucción de filas partidas
    # ------------------------------------------------------------------
    def _rebuild_broken_rows(self, markdown: str) -> str:
        """
        Une líneas que pertenecen a la misma fila de tabla pero fueron
        separadas por saltos de línea dentro de celdas.
        """
        lines = markdown.splitlines()
        output: List[str] = []
        buffer: List[str] = []

        def flush():
            nonlocal buffer
            if buffer:
                merged = " ".join(buffer).strip()
                # Normalizar pipes múltiples generados por la unión
                merged = re.sub(r"\|\s*\|+", "|", merged)
                output.append(merged)
                buffer = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and not stripped.endswith("|"):
                # Posible continuación de fila
                buffer.append(stripped)
            elif stripped.startswith("|") and stripped.endswith("|"):
                if buffer:
                    buffer.append(stripped)
                    flush()
                else:
                    output.append(stripped)
            else:
                flush()
                output.append(line)

        flush()
        return "\n".join(output)

    # ------------------------------------------------------------------
    # Reparación del bloque de tabla
    # ------------------------------------------------------------------
    def _repair_table_block(self, lines: List[str]) -> List[str]:
        if not lines:
            return lines

        # 1. Quitar filas de separador completamente vacías
        cleaned = self._remove_empty_separator_rows(lines)

        # 2. Normalizar filas de separador
        normalized = self._normalize_separator_rows(cleaned)

        # 3. Intentar fusionar filas que parecen estar partidas
        merged = self._merge_broken_rows(normalized)

        # 4. Intentar expandir celdas con números apilados (patrón año/n/%)
        expanded = self._expand_stacked_numbers(merged)

        # Decisión conservadora
        if self._is_improvement(lines, expanded):
            return expanded
        return normalized

    @staticmethod
    def _remove_empty_separator_rows(lines: List[str]) -> List[str]:
        result = []
        for line in lines:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(c == "" for c in cells):
                continue
            result.append(line)
        return result

    @staticmethod
    def _normalize_separator_rows(lines: List[str]) -> List[str]:
        result = []
        for line in lines:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.match(r"^[-=:]+$", c) or c == "" for c in cells):
                result.append("|" + "|".join(["---" if c else "" for c in cells]) + "|")
            else:
                result.append(line)
        return result

    # ------------------------------------------------------------------
    # Fusión de filas
    # ------------------------------------------------------------------
    def _merge_broken_rows(self, lines: List[str]) -> List[str]:
        if len(lines) < 2:
            return lines

        parsed = [self._parse_row(line) for line in lines]
        result: List[List[str]] = []
        current = None

        for cells in parsed:
            if current is None:
                current = cells
                continue

            if self._can_merge(current, cells):
                current = self._merge_rows(current, cells)
            else:
                result.append(current)
                current = cells

        if current:
            result.append(current)

        return [self._render_row(row) for row in result]

    @staticmethod
    def _parse_row(line: str) -> List[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    @staticmethod
    def _render_row(cells: List[str]) -> str:
        return "|" + "|".join(f" {c} " if c else " " for c in cells) + "|"

    def _can_merge(self, upper: List[str], lower: List[str]) -> bool:
        if len(upper) != len(lower):
            return False

        # No fusionar si alguna es separador
        if all(re.match(r"^[-=:]+$", c) or c == "" for c in upper):
            return False
        if all(re.match(r"^[-=:]+$", c) or c == "" for c in lower):
            return False

        # Contar celdas complementarias
        complement = sum(1 for u, l in zip(upper, lower) if (u == "" and l) or (u and l == ""))
        if complement >= max(len(upper) // 2, 2):
            return True

        return False

    @staticmethod
    def _merge_rows(upper: List[str], lower: List[str]) -> List[str]:
        merged = []
        for u, l in zip(upper, lower):
            if u and l:
                sep = "" if u.endswith(("-", "/")) or l.startswith(("-", "/")) else " "
                merged.append((u + sep + l).strip())
            else:
                merged.append(u or l)
        return merged

    # ------------------------------------------------------------------
    # Expansión de números apilados (año / n / %)
    # ------------------------------------------------------------------
    def _expand_stacked_numbers(self, lines: List[str]) -> List[str]:
        # Versión simplificada pero más efectiva que la anterior
        parsed = [self._parse_row(line) for line in lines]
        result = list(parsed)

        year_row_idx = self._find_year_header(parsed)
        if year_row_idx is None:
            return lines

        years = self._extract_years(parsed[year_row_idx])
        if not years:
            return lines

        # Buscar filas con celdas que tengan múltiples líneas de números
        for i in range(year_row_idx + 1, len(parsed)):
            row = result[i]
            for j, cell in enumerate(row):
                values = [v.strip() for v in cell.splitlines() if v.strip()]
                if len(values) == len(years) and all(self._NUMBER_CELL_RE.match(v) for v in values):
                    # Expandir esta celda
                    new_rows = []
                    for k, val in enumerate(values):
                        new_row = list(row)
                        new_row[j] = val
                        new_rows.append(new_row)

                    # Reemplazar la fila original por las nuevas
                    result = result[:i] + new_rows + result[i+1:]
                    break

        return [self._render_row(row) for row in result]

    def _find_year_header(self, parsed: List[List[str]]) -> int | None:
        for i, row in enumerate(parsed):
            years = self._YEAR_RE.findall(" ".join(row))
            if len(years) >= 2:
                return i
        return None

    @staticmethod
    def _extract_years(row: List[str]) -> List[int]:
        years = sorted({int(y) for y in TablePostProcessor._YEAR_RE.findall(" ".join(row))})
        return years if len(years) >= 2 else []

    # ------------------------------------------------------------------
    # Decisión final
    # ------------------------------------------------------------------
    @staticmethod
    def _is_improvement(original: List[str], repaired: List[str]) -> bool:
        if len(repaired) < len(original) * 0.7:
            return False
        if len(repaired) > len(original) * 5:
            return False
        return True
