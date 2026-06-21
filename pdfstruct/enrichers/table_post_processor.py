"""
pdfstruct/enrichers/table_post_processor.py

Post-procesador de tablas Markdown.

Objetivo: reparar tablas que PyMuPDF4LLM suele dejar malformadas,
especialmente tablas con años, columnas n/% y filas partidas.
"""

from __future__ import annotations

import re
from typing import List, Tuple


class TablePostProcessor:
    """Repara bloques de tabla Markdown con heurísticas."""

    _YEAR_RE = re.compile(r"\b(20\d{2})\b")
    _NUMBER_RE = re.compile(r"^\*?\d+(?:[.,]\d+)?\*?$")

    def __init__(self):
        from .table_extractor import TableReconstructor
        self._reconstructor = TableReconstructor()

    def process(self, markdown: str) -> str:
        """
        Procesa el markdown completo buscando bloques de tabla y reparándolos.
        """
        lines = markdown.splitlines()
        output: List[str] = []
        buffer: List[str] = []

        for line in lines:
            if self._is_table_line_or_continuation(line):
                buffer.append(line)
            else:
                if buffer:
                    output.extend(self._process_table_buffer(buffer))
                    buffer = []
                output.append(line)

        if buffer:
            output.extend(self._process_table_buffer(buffer))

        return "\n".join(output)

    @staticmethod
    def _is_table_line_or_continuation(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if stripped.startswith("|"):
            return True
        # Años, n/% y números sueltos son continuación de celda de tabla
        if re.match(r"^\*\*20\d{2}\*\*$", stripped):
            return True
        if stripped in ("**_n_**", "**n**", "**N**", "**%**"):
            return True
        if re.match(r"^\*?\d+[\.,]?\d*\*?|%$", stripped):
            return True
        return False

    def _process_table_buffer(self, buffer: List[str]) -> List[str]:
        """Reconstruye un bloque de tabla acumulado."""
        # Primero, unir líneas sueltas que son continuación de celda dentro
        # de una misma fila de tabla. Usamos espacios para que cada fila
        # quede en una sola línea Markdown.
        joined: List[str] = []
        for line in buffer:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("|"):
                if joined and not joined[-1].strip().endswith("|"):
                    joined[-1] = joined[-1] + " " + line
                else:
                    joined.append(line)
            elif joined:
                joined[-1] = joined[-1] + " " + line
            else:
                joined.append(line)

        # 1. Unir líneas sueltas que pertenecen a la misma fila/celda
        joined = self._join_loose_lines(joined)

        # 2. Construir filas completas de tabla
        rows = self._build_complete_rows(joined)

        if not rows:
            return buffer

        # 3. Si es tabla con años, reconstruir completamente
        if self._is_year_table(rows):
            reconstructed = self._reconstruct_year_table(rows)
            if reconstructed:
                # Preservar líneas no-tabla (título, nota, pie) que rodean la tabla
                before, after = self._split_non_table_lines(buffer)
                result_lines = before + reconstructed.splitlines() + after
                if self._is_improvement(rows, result_lines):
                    return result_lines

        # 4. Intentar reconstructor externo
        table_md = "\n".join(rows)
        try:
            external = self._reconstructor.process(table_md)
            if external != table_md:
                return external.splitlines()
        except Exception:
            pass

        # 5. Reparaciones conservadoras
        return self._repair_table_block(rows)

    @staticmethod
    def _split_non_table_lines(buffer: List[str]) -> Tuple[List[str], List[str]]:
        """Separa líneas de título/encabezado y notas/pie del bloque de tabla."""
        before: List[str] = []
        after: List[str] = []
        table_started = False
        table_rows_seen = 0
        table_ended = False

        for line in buffer:
            stripped = line.strip()
            is_table_line = stripped.startswith("|") or (table_started and stripped.startswith("**"))

            if not table_started:
                if is_table_line:
                    table_started = True
                else:
                    before.append(line)
            elif table_ended:
                after.append(line)
            else:
                if is_table_line:
                    table_rows_seen += 1
                else:
                    if table_rows_seen >= 2 and not stripped:
                        table_ended = True
                    elif table_rows_seen >= 2:
                        # Notas/parrafo que sigue a la tabla
                        table_ended = True
                        after.append(line)
                    else:
                        # Aún dentro del encabezado previo
                        before.append(line)

        return before, after

    # ------------------------------------------------------------------
    # Unión de líneas sueltas
    # ------------------------------------------------------------------
    @staticmethod
    def _join_loose_lines(lines: List[str]) -> List[str]:
        """
        Une líneas sueltas que son continuación de una celda anterior.

        PyMuPDF4LLM parte las celdas multilínea en líneas separadas. Para poder
        reconstruir la tabla, unimos esas líneas con espacios de modo que cada
        fila de tabla quede en una única línea Markdown.
        """
        joined: List[str] = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                continue

            is_table_row = stripped.startswith("|")
            is_year_or_header = (
                re.match(r"^\*\*20\d{2}\*\*$", stripped)
                or stripped in ("**_n_**", "**n**", "**N**", "**%**")
            )

            if is_table_row:
                joined.append(line)
            elif joined and (is_year_or_header or not stripped.startswith("|")):
                # Continuación de la línea de tabla anterior. Si la línea
                # anterior termina en '|' y la nueva empieza con número,
                # es una nueva celda de la misma fila: separar con '|'.
                prev = joined[-1].rstrip()
                if prev.endswith("|") and re.match(r"^\*?\d+[\.,]?\d*\*?|%$", stripped):
                    joined[-1] = prev + " " + line
                else:
                    joined[-1] = prev + " " + line
            else:
                joined.append(line)

        return joined

    @staticmethod
    def _build_complete_rows(lines: List[str]) -> List[str]:
        """
        Construye filas de tabla markdown completas a partir de líneas sueltas.

        Una fila puede estar partida en varias líneas que empiezan con '|'.
        Las unimos concatenando celdas.
        """
        rows: List[str] = []
        current: str | None = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("|"):
                if current is None:
                    current = line
                else:
                    # Concatenar celdas de continuación
                    current = current.rstrip() + " " + line.lstrip()
                if stripped.endswith("|"):
                    rows.append(current)
                    current = None
            else:
                # Línea suelta sin '|'
                if current is not None:
                    current = current + "\n" + line
                else:
                    # Ignorar líneas sueltas sin contexto de tabla
                    pass

        if current is not None:
            rows.append(current)

        return rows

    @staticmethod
    def _render_row(cells: List[str]) -> str:
        return "|" + "|".join(f" {c} " if c else " " for c in cells) + "|"

    @staticmethod
    def _parse_row(line: str) -> List[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    # ------------------------------------------------------------------
    # Reconstrucción de tablas con años
    # ------------------------------------------------------------------
    def _is_year_table(self, rows: List[str]) -> bool:
        for row in rows[:5]:
            years = sorted({int(y) for y in self._YEAR_RE.findall(row)})
            if len(years) >= 2:
                return True
        return False

    def _reconstruct_year_table(self, rows: List[str]) -> str | None:
        """
        Reconstruye una tabla con años apilados en formato ancho:
        | Dimensión | Indicador | 2017 n | 2017 % | ... |

        Soporta tanto tablas Markdown con filas partidas verticalmente como
        tablas ya renderizadas con saltos `<br>` dentro de las celdas.
        """
        parsed = [self._parse_row(r) for r in rows if r.strip().startswith("|")]
        if not parsed:
            return None

        years: List[int] = []
        for row in parsed[:5]:
            years = sorted({int(y) for y in self._YEAR_RE.findall(" ".join(row))})
            if len(years) >= 2:
                break

        if not years:
            return None

        # Detectar si el header tiene sub-columnas n/% (una por año) o solo años.
        has_subheader_n_pct = self._has_n_pct_subheader(parsed, years)

        if has_subheader_n_pct:
            header = ["Dimensión", "Indicador"] + [f"{y} n" for y in years] + [f"{y} %" for y in years]
        else:
            header = ["Dimensión", "Indicador"] + [str(y) for y in years]
        result = [self._render_row(header), self._render_row(["---"] * len(header))]

        current_dimension = ""

        for row in parsed:
            if all(re.match(r"^[-=:]+$", c) or c == "" for c in row):
                continue

            row_text = " ".join(row)
            if "Indicadores" in row_text and not any(
                self._NUMBER_RE.match(t) for cell in row for t in self._cell_tokens(cell)
            ):
                continue

            # Encontrar todas las celdas numéricas consecutivas al final de la fila
            numeric_cols: List[int] = []
            for i in range(len(row) - 1, -1, -1):
                tokens = self._cell_tokens(row[i])
                expected = len(years) * 2 if has_subheader_n_pct else len(years)
                if len(tokens) == expected and all(
                    self._NUMBER_RE.match(t) or t == "%" for t in tokens
                ):
                    numeric_cols.append(i)
                else:
                    break

            if not numeric_cols:
                continue

            numeric_cols = sorted(numeric_cols)
            if len(numeric_cols) != len(years):
                # No hay una celda por año; usar solo la última celda numérica
                numeric_cols = [numeric_cols[-1]]

            values: List[str] = []
            for col in numeric_cols:
                tokens = self._cell_tokens(row[col])
                if has_subheader_n_pct:
                    pairs = self._extract_pairs(tokens, years)
                    if not pairs:
                        values = []
                        break
                    values.extend([str(p[0]) for p in pairs])
                    values.extend([str(p[1]) for p in pairs])
                else:
                    values.extend(tokens)

            if not values:
                continue

            prefix = row[:numeric_cols[0]]
            flat = " ".join(" ".join(self._cell_tokens(c)) for c in prefix if c.strip()).strip()
            if not flat:
                continue

            dimension, indicator = self._split_dimension_indicator(flat, current_dimension)
            if dimension:
                current_dimension = dimension

            result.append(self._render_row([current_dimension, indicator] + values))

        return "\n".join(result) if len(result) > 2 else None

    @staticmethod
    def _has_n_pct_subheader(parsed: List[List[str]], years: List[int]) -> bool:
        """Detecta si la tabla tiene subheader n/% apilado por año."""
        for row in parsed[:5]:
            row_text = " ".join(row)
            n_pct_tokens = [t for t in row_text.replace("<br>", " ").split() if t in ("**_n_**", "**%**", "_n_", "%")]
            if len(n_pct_tokens) >= len(years):
                return True
        return False

    @staticmethod
    def _cell_tokens(cell: str) -> List[str]:
        """Divide una celda en tokens, manejando saltos de línea y <br>."""
        normalized = cell.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        return [t.strip() for t in normalized.replace("\n", " ").split() if t.strip()]

    @staticmethod
    def _extract_pairs(tokens: List[str], years: List[int]) -> List[Tuple[str, str]]:
        if len(tokens) == len(years):
            return [(t, "") for t in tokens]
        if len(tokens) == len(years) * 2:
            return [(tokens[i], tokens[i + 1]) for i in range(0, len(tokens), 2)]
        return []

    @staticmethod
    def _split_dimension_indicator(prefix: str, current_dimension: str) -> Tuple[str, str]:
        known_dimensions = [
            "Reglamentación y acreditación",
            "Número de trabajadores activos",
            "Flujos de trabajadores",
            "Características del empleo, condiciones de trabajo y remuneración",
            "Combinación de competencias para modelos de atención",
            "Educación y capacitación",
            "Disponibilidad de trabajadores de salud",
            "Distribución de trabajadores",
            "Producción de trabajadores de salud",
        ]

        for dim in known_dimensions:
            if prefix.startswith(dim):
                return dim, prefix[len(dim):].strip()

        if "\n" in prefix:
            parts = [p.strip() for p in prefix.split("\n", 1)]
            return parts[0], parts[1]

        if len(prefix) <= 40 and prefix and prefix == prefix.upper():
            return prefix, ""

        return current_dimension, prefix

    # ------------------------------------------------------------------
    # Reparación conservadora del bloque de tabla
    # ------------------------------------------------------------------
    def _repair_table_block(self, lines: List[str]) -> List[str]:
        if not lines:
            return lines

        cleaned = self._remove_empty_separator_rows(lines)
        normalized = self._normalize_separator_rows(cleaned)
        merged = self._merge_broken_rows(normalized)
        expanded = self._expand_stacked_numbers(merged)

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

    def _can_merge(self, upper: List[str], lower: List[str]) -> bool:
        if len(upper) != len(lower):
            return False

        if all(re.match(r"^[-=:]+$", c) or c == "" for c in upper):
            return False
        if all(re.match(r"^[-=:]+$", c) or c == "" for c in lower):
            return False

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

    def _expand_stacked_numbers(self, lines: List[str]) -> List[str]:
        parsed = [self._parse_row(line) for line in lines]
        result = list(parsed)

        year_row_idx = self._find_year_header(parsed)
        if year_row_idx is None:
            return lines

        years = self._extract_years(parsed[year_row_idx])
        if not years:
            return lines

        for i in range(year_row_idx + 1, len(parsed)):
            row = result[i]
            for j, cell in enumerate(row):
                values = [v.strip() for v in cell.splitlines() if v.strip()]
                if len(values) == len(years) and all(self._NUMBER_RE.match(v) for v in values):
                    new_rows = []
                    for val in values:
                        new_row = list(row)
                        new_row[j] = val
                        new_rows.append(new_row)
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

    @staticmethod
    def _is_improvement(original: List[str], repaired: List[str]) -> bool:
        if len(repaired) < len(original) * 0.7:
            return False
        if len(repaired) > len(original) * 5:
            return False
        return True
