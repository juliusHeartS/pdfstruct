"""
pdfstruct/enrichers/table_extractor.py

Extracción y reconstrucción de tablas usando pdfplumber.

Proporciona utilidades para detectar tablas en una página de PDF y
convertirlas a Markdown de forma limpia y estructurada.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

import pdfplumber


class TableExtractor:
    """Extrae tablas de un PDF usando pdfplumber."""

    def __init__(self):
        self._default_settings = {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "snap_tolerance": 4,
            "join_tolerance": 4,
            "edge_min_length": 8,
            "min_words_vertical": 1,
            "min_words_horizontal": 1,
            "text_tolerance": 4,
            "text_x_tolerance": 4,
            "text_y_tolerance": 4,
        }

    def extract_page_tables(
        self, pdf_path: str | Path, page_index: int
    ) -> List[List[List[str]]]:
        """
        Extrae todas las tablas de una página específica.

        Returns:
            Lista de tablas, cada una es una lista de filas de celdas de texto.
        """
        with pdfplumber.open(str(pdf_path)) as doc:
            if page_index >= len(doc.pages):
                return []
            page = doc.pages[page_index]
            tables = page.find_tables(self._default_settings)
            result = []
            for table in tables:
                rows = table.extract()
                if rows:
                    result.append(rows)
            return result

    @staticmethod
    def table_to_markdown(rows: List[List[str]]) -> str:
        """
        Convierte filas de tabla extraídas por pdfplumber a Markdown.

        Limpia caracteres de control, normaliza espacios y genera una tabla
        markdown bien formada.
        """
        if not rows:
            return ""

        # Limpiar cada celda
        cleaned_rows = []
        for row in rows:
            cleaned = [TableExtractor._clean_cell(cell) for cell in row]
            cleaned_rows.append(cleaned)

        # Calcular ancho máximo por columna
        num_cols = max(len(r) for r in cleaned_rows)

        # Normalizar filas para que todas tengan el mismo número de columnas
        normalized = []
        for row in cleaned_rows:
            if len(row) < num_cols:
                row = row + [""] * (num_cols - len(row))
            elif len(row) > num_cols:
                row = row[:num_cols]
            normalized.append(row)

        if not normalized:
            return ""

        lines = []
        lines.append("|" + "|".join(f" {c} " for c in normalized[0]) + "|")
        lines.append("|" + "|".join(" --- " for _ in normalized[0]) + "|")
        for row in normalized[1:]:
            lines.append("|" + "|".join(f" {c} " for c in row) + "|")

        return "\n".join(lines)

    @staticmethod
    def _clean_cell(value) -> str:
        if value is None:
            return ""
        text = str(value)

        # Eliminar caracteres de control
        text = "".join(c if ord(c) >= 32 or c in "\n\t" else " " for c in text)

        # Normalizar espacios
        text = re.sub(r"\s+", " ", text).strip()

        # Unir palabras partidas por caracteres de control raros que ya convertimos a espacio
        text = re.sub(r"\b(\w) \w\b", r"\1", text)  # cuidadoso, no siempre deseado

        return text

    @staticmethod
    def is_valid_table(rows: List[List[str]]) -> bool:
        """
        Heurística de confianza: ¿la tabla extraída parece usable?

        Criterios:
        - Al menos 2 filas.
        - Al menos 2 columnas.
        - No todas las celdas vacías.
        - Filas con número de columnas razonablemente consistente.
        """
        if not rows or len(rows) < 2:
            return False

        num_cols = [len(r) for r in rows]
        if max(num_cols) < 2:
            return False

        # Al menos algunas celdas no vacías
        non_empty = sum(1 for r in rows for c in r if c and str(c).strip())
        if non_empty < len(rows):
            return False

        # Variación de columnas no demasiado grande
        if max(num_cols) - min(num_cols) > 2:
            return False

        return True


class TableReconstructor:
    """
    Reconstructor heurístico de tablas Markdown rotas por PyMuPDF4LLM.

    Se especializa en el patrón:
    - Encabezado con años apilados verticalmente (2017, 2018, ..., 2021).
    - Sub-encabezado con pares n / %.
    - Filas de datos con indicadores en las primeras columnas y números apilados.
    """

    _YEAR_RE = re.compile(r"\b(20\d{2})\b")
    _NUMBER_RE = re.compile(r"^\*?\d+(?:[.,]\d+)?\*?$")

    def process(self, markdown_table: str) -> str:
        """
        Intenta reconstruir una tabla Markdown rota.

        Si no detecta el patrón año/n/%, devuelve la tabla original.
        """
        lines = markdown_table.splitlines()
        if len(lines) < 4:
            return markdown_table

        parsed = self._parse_rows(lines)
        years = self._find_stacked_years(parsed)
        if not years:
            return markdown_table

        # Filtrar filas de separador y encabezados previos antes de procesar datos.
        content_rows = [
            row
            for row in parsed
            if not all(re.match(r"^[-=:]+$", c) or c == "" for c in row)
        ]

        # Procesar filas de datos
        data_rows = self._extract_data_rows(content_rows, years)
        if not data_rows:
            return markdown_table

        # Reconstruir encabezado
        new_header = (
            ["Dimensión", "Indicador"]
            + [f"{y} n" for y in years]
            + [f"{y} %" for y in years]
        )
        separator = ["---"] * len(new_header)

        result_lines = [
            self._render_row(new_header),
            self._render_row(separator),
        ]
        for row in data_rows:
            result_lines.append(self._render_row(row))

        return "\n".join(result_lines)

    @staticmethod
    def _parse_rows(lines: List[str]) -> List[List[str]]:
        """Parsea líneas de tabla markdown a celdas, preservando saltos internos."""
        parsed = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                # No dividir celdas por '\n' interno; conservar como celda multilínea.
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                parsed.append(cells)
        return parsed

    @staticmethod
    def _render_row(cells: List[str]) -> str:
        return "|" + "|".join(f" {c} " for c in cells) + "|"

    def _find_stacked_years(self, parsed: List[List[str]]) -> List[int]:
        """Busca un encabezado con años apilados verticalmente."""
        # Buscar en las primeras filas una celda que contenga años en líneas separadas
        for row in parsed[:5]:
            for cell in row:
                lines = [line.strip() for line in cell.splitlines() if line.strip()]
                years = []
                for line in lines:
                    matches = self._YEAR_RE.findall(line)
                    years.extend(int(m) for m in matches)
                if len(years) >= 2:
                    return sorted(set(years))

        # También buscar años en texto plano dentro de celdas (formato unido)
        for row in parsed[:5]:
            text = " ".join(row)
            years = sorted({int(y) for y in self._YEAR_RE.findall(text)})
            if len(years) >= 2:
                return years
        return []

    def _extract_data_rows(
        self, parsed: List[List[str]], years: List[int]
    ) -> List[List[str]]:
        """
        Extrae filas de datos reconstruyendo dimensión, indicador y pares n/%.

        Asume que las primeras 2-3 columnas son texto (dimensión/indicador) y
        la última columna contiene los números apilados.
        """
        data_rows = []
        current_dimension = ""
        data_start_found = False

        for row in parsed:
            # Detectar fila que marca el inicio real de datos
            numeric_cells = [
                i for i, cell in enumerate(row) if self._is_stacked_numbers(cell, years)
            ]
            if not data_start_found:
                if not numeric_cells:
                    continue
                # Saltar filas que solo contienen el encabezado "Indicadores"
                if (
                    len(numeric_cells) == 1
                    and len(row) == 2
                    and row[0].strip().lower() in ("indicadores", "indicador")
                ):
                    continue
                data_start_found = True

            if not numeric_cells:
                continue

            # La celda numérica más a la derecha suele contener los datos
            data_col = numeric_cells[-1]
            values = self._extract_number_pairs(row[data_col], years)
            if not values:
                continue

            # Columnas anteriores: dimensión e indicador
            prefix = row[:data_col]
            flat_prefix = " ".join(
                " ".join(c.splitlines()) for c in prefix if c.strip()
            ).strip()
            if not flat_prefix:
                continue

            # Separar dimensión e indicador
            dimension, indicator = self._split_dimension_indicator(
                flat_prefix, current_dimension
            )
            if dimension and dimension != current_dimension:
                current_dimension = dimension

            n_values = [str(v[0]) for v in values]
            p_values = [str(v[1]) for v in values]

            data_rows.append([current_dimension, indicator] + n_values + p_values)

        return data_rows

    def _is_stacked_numbers(self, cell: str, years: List[int]) -> bool:
        """¿La celda contiene números apilados correspondientes a los años?"""
        values = self._parse_number_tokens(cell)
        if not values:
            return False
        # Permitir tokens % como parte de pares n/%
        numeric_like = [v for v in values if self._NUMBER_RE.match(v) or v == "%"]
        if len(numeric_like) != len(values):
            return False
        # Patrón aceptado: N números (uno por año) o 2*N valores alternados
        return len(values) in (len(years), len(years) * 2)

    def _extract_number_pairs(
        self, cell: str, years: List[int]
    ) -> List[Tuple[str, str]]:
        """Extrae pares (n, %) de una celda con números apilados."""
        values = self._parse_number_tokens(cell)
        if len(values) == len(years):
            # Solo números, sin %
            return [(v, "") for v in values]
        if len(values) == len(years) * 2:
            pairs = []
            for i in range(0, len(values), 2):
                pairs.append((values[i], values[i + 1]))
            return pairs
        return []

    @staticmethod
    def _parse_number_tokens(cell: str) -> List[str]:
        """Extrae tokens numéricos o % de una celda, ya sea por líneas o espacios."""
        # Primero intentar por saltos de línea
        lines = [line.strip() for line in cell.splitlines() if line.strip()]
        if lines:
            # Si cada línea es un token simple, usar líneas
            if all(len(line.split()) <= 1 for line in lines):
                return lines
            # Si las líneas concatenadas forman tokens, unirlas
            flat = " ".join(lines)
        else:
            flat = cell
        # Separar por espacios y quitar vacíos
        tokens = [t.strip() for t in flat.replace(",", " ").split() if t.strip()]
        return tokens

    @staticmethod
    def _has_only_numbers(values: List[str]) -> bool:
        """¿Todos los valores son numéricos (sin %)?"""
        return all(
            not v.endswith("%") and TableReconstructor._NUMBER_RE.match(v)
            for v in values
        )

    @staticmethod
    def _split_dimension_indicator(
        prefix: str, current_dimension: str
    ) -> Tuple[str, str]:
        """
        Separa dimensión e indicador de un texto plano.

        Heurística: si el texto parece contener una dimensión conocida al inicio
        (como "Reglamentación y acreditación"), usarla como dimensión.
        Si no, tratar todo como indicador y mantener la dimensión actual.
        """
        # Lista de posibles dimensiones extraídas de cuadros de salud.
        known_dimensions = [
            "Reglamentación y acreditación",
            "Número de trabajadores activos",
            "Flujos de trabajadores",
            "Características del empleo, condiciones de trabajo y remuneración",
            "Combinación de competencias para modelos de atención",
            "Educación y capacitación",
            "Disponibilidad de trabajadores de salud",
        ]

        for dim in known_dimensions:
            if prefix.startswith(dim):
                return dim, prefix[len(dim) :].strip()

        # Si el texto contiene un salto de línea, separar por la primera línea
        if "\n" in prefix:
            parts = [p.strip() for p in prefix.split("\n", 1)]
            return parts[0], parts[1]

        # Si el texto es corto y todo mayúsculas, considerarlo dimensión
        if len(prefix) <= 40 and prefix and prefix == prefix.upper():
            return prefix, ""

        return current_dimension, prefix
