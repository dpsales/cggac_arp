"""Parser XLSX para carga de ARP (dados_cggac)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
import html
import re
import zipfile


_ROW_RE = re.compile(r'<row[^>]*r="(\d+)"[^>]*>(.*?)</row>', re.DOTALL)
_CELL_RE = re.compile(r'<c[^>]*r="([A-Z]+)\d+"[^>]*?(?:t="([^"]+)")?[^>]*>(.*?)</c>', re.DOTALL)
_TEXT_RE = re.compile(r'<t(?:\s[^>]*)?>(.*?)</t>', re.DOTALL)
_VALUE_RE = re.compile(r'<v>(.*?)</v>', re.DOTALL)


HEADER_TO_FIELD = {
    "numero_pregao": "numero_pregao",
    "num_controle_pncp": "num_controle_pncp",
    "srk_compra": "srk_compra",
    "dsc_objeto_arp": "dsc_objeto_arp",
    "cod_id_uasg_origem_compra": "cod_id_uasg_origem_compra",
    "num_ano": "num_ano",
    "num_arp": "num_arp",
    "num_processo_compra": "num_processo_compra",
    "srk_uasg_origem_compra": "srk_uasg_origem_compra",
    "srk_orgao_compra": "srk_orgao_compra",
    "srk_uasg_subrrogada_compra": "srk_uasg_subrrogada_compra",
    "srk_uasg_beneficiaria_compra": "srk_uasg_beneficiaria_compra",
    "srk_arp_item": "srk_arp_item",
    "srk_solicitacao": "srk_solicitacao",
    "srk_solicitacao_item": "srk_solicitacao_item",
    "qtd_solicitada": "qtd_solicitada",
    "qtd_aprovada": "qtd_aprovada",
    "srk_uasg_solicitacao": "srk_uasg_solicitacao",
    "item_arp": "item_arp",
    "srk_fornecedor": "srk_fornecedor",
    "srk_compra_item": "srk_compra_item",
    "srk_dominio_item_tipo_item": "srk_dominio_item_tipo_item",
    "qtd_homologada_vencedor_fornecedor": "qtd_homologada_vencedor_fornecedor",
    "vlr_unitario_fornecedor": "vlr_unitario_fornecedor",
    "vlr_negociado_fornecedor": "vlr_negociado_fornecedor",
    "qtd_empenhada_fornecedor": "qtd_empenhada_fornecedor",
    "qtd_total_compra_item": "qtd_total_compra_item",
    "qtd_maximo_adesao_compra_item": "qtd_maximo_adesao_compra_item",
    "num_cpf_cnpj_fornecedor": "num_cpf_cnpj_fornecedor",
    "dsc_detalhada": "dsc_detalhada",
    "cod_catmatser_item": "cod_catmatser_item",
    "ind_permite_carona": "ind_permite_carona",
    "dth_vigencia_inicial_arp": "dth_vigencia_inicial_arp",
    "dth_assinatura_arp": "dth_assinatura_arp",
    "dth_vigencia_final_arp": "dth_vigencia_final_arp",
    "vlr_total_arp": "vlr_total_arp",
}

INT_FIELDS = {
    "srk_compra",
    "cod_id_uasg_origem_compra",
    "num_ano",
    "srk_uasg_origem_compra",
    "srk_orgao_compra",
    "srk_uasg_subrrogada_compra",
    "srk_uasg_beneficiaria_compra",
    "srk_arp_item",
    "srk_solicitacao",
    "srk_solicitacao_item",
    "srk_uasg_solicitacao",
    "item_arp",
    "srk_fornecedor",
    "srk_compra_item",
    "srk_dominio_item_tipo_item",
}

DECIMAL_FIELDS = {
    "qtd_solicitada",
    "qtd_aprovada",
    "qtd_homologada_vencedor_fornecedor",
    "vlr_unitario_fornecedor",
    "vlr_negociado_fornecedor",
    "qtd_empenhada_fornecedor",
    "qtd_total_compra_item",
    "qtd_maximo_adesao_compra_item",
    "vlr_total_arp",
}

DATE_FIELDS = {
    "dth_vigencia_inicial_arp",
    "dth_assinatura_arp",
    "dth_vigencia_final_arp",
}


def _col_to_index(col: str) -> int:
    value = 0
    for c in col:
        value = value * 26 + (ord(c) - ord("A") + 1)
    return value - 1


def _cell_text(inner_xml: str) -> str:
    if "<is>" in inner_xml:
        parts = _TEXT_RE.findall(inner_xml)
        return html.unescape("".join(parts)).strip()
    m = _VALUE_RE.search(inner_xml)
    if not m:
        return ""
    text = html.unescape(m.group(1)).strip()
    return "" if text.lower() == "null" else text


def _as_int(value: str):
    if not value:
        return None
    try:
        return int(Decimal(value))
    except (InvalidOperation, ValueError):
        return None


def _as_decimal(value: str):
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _as_date(value: str):
    if not value:
        return None
    try:
        num = Decimal(value)
        base = date(1899, 12, 30)
        return base + timedelta(days=int(num))
    except InvalidOperation:
        pass

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "sim", "s", "x", "yes", "y"}


def ler_xlsx_arp(caminho: Path, aba: int = 0):
    """Lê XLSX da CGGAC e retorna (registros, avisos)."""
    del aba

    registros = []
    avisos = []

    with zipfile.ZipFile(Path(caminho), "r") as zf:
        sheet_path = "xl/worksheets/sheet1.xml"
        if sheet_path not in zf.namelist():
            raise FileNotFoundError("sheet1.xml não encontrado no XLSX")

        header_map = {}
        with zf.open(sheet_path) as f:
            buffer = ""
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                buffer += chunk.decode("utf-8", errors="replace")
                last_end = 0

                for m in _ROW_RE.finditer(buffer):
                    last_end = m.end()
                    row_num = int(m.group(1))
                    row_xml = m.group(2)

                    cells = []
                    for cm in _CELL_RE.finditer(row_xml):
                        col = cm.group(1)
                        idx = _col_to_index(col)
                        text = _cell_text(cm.group(3))
                        cells.append((idx, text))

                    if row_num == 1:
                        for idx, val in cells:
                            key = val.strip().lower()
                            field = HEADER_TO_FIELD.get(key)
                            if field:
                                header_map[idx] = field
                        if not header_map:
                            avisos.append("Nenhuma coluna reconhecida no cabeçalho")
                        continue

                    if not header_map:
                        continue

                    data = {}
                    for idx, val in cells:
                        field = header_map.get(idx)
                        if not field:
                            continue
                        if field in INT_FIELDS:
                            data[field] = _as_int(val)
                        elif field in DECIMAL_FIELDS:
                            data[field] = _as_decimal(val)
                        elif field in DATE_FIELDS:
                            data[field] = _as_date(val)
                        elif field == "ind_permite_carona":
                            data[field] = _as_bool(val)
                        else:
                            data[field] = val

                    if data:
                        registros.append(data)

                buffer = buffer[last_end:]

    return registros, avisos
