from datetime import timedelta
from functools import lru_cache
from pathlib import Path
import html
import re
import zipfile
from urllib.parse import urlencode

from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from dados.models import AtaRegistroPreco, CargaLog


_XLSX_ROW_RE = re.compile(r'<row[^>]*r="(\d+)"[^>]*>(.*?)</row>', re.DOTALL)
_XLSX_CELL_RE = re.compile(r'<c[^>]*r="([A-Z]+)\d+"[^>]*?(?:t="([^"]+)")?[^>]*>(.*?)</c>', re.DOTALL)
_XLSX_TEXT_RE = re.compile(r'<t(?:\s[^>]*)?>(.*?)</t>', re.DOTALL)
_XLSX_VALUE_RE = re.compile(r'<v>(.*?)</v>', re.DOTALL)
_SOLICITACOES_XLSX2_MAX_ROWS = 5000
_SOLICITACOES_XLSX2_PAGE_SIZE = 25


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _filtros_base(request):
    qs = AtaRegistroPreco.objects.all()
    hoje = timezone.now().date()

    ano = _to_int(request.GET.get('ano'))
    carona = request.GET.get('carona')
    uasg = _to_int(request.GET.get('uasg'))
    fornecedor = request.GET.get('fornecedor')
    vigencia = request.GET.get('vigencia')

    if ano:
        qs = qs.filter(num_ano=ano)
    if carona in ('1', '0'):
        qs = qs.filter(ind_permite_carona=(carona == '1'))
    if uasg:
        qs = qs.filter(cod_id_uasg_origem_compra=uasg)
    if fornecedor:
        qs = qs.filter(num_cpf_cnpj_fornecedor=fornecedor)
    if vigencia == 'vigente':
        qs = qs.filter(
            dth_vigencia_inicial_arp__isnull=False,
            dth_vigencia_final_arp__isnull=False,
            dth_vigencia_inicial_arp__lte=hoje,
            dth_vigencia_final_arp__gte=hoje,
        )
    elif vigencia == 'vencida':
        qs = qs.filter(
            dth_vigencia_final_arp__isnull=False,
            dth_vigencia_final_arp__lt=hoje,
        )
    elif vigencia == 'expira_30':
        qs = qs.filter(
            dth_vigencia_final_arp__isnull=False,
            dth_vigencia_final_arp__gte=hoje,
            dth_vigencia_final_arp__lte=hoje + timedelta(days=30),
        )
    elif vigencia == 'sem_vigencia':
        qs = qs.filter(
            Q(dth_vigencia_inicial_arp__isnull=True) | Q(dth_vigencia_final_arp__isnull=True)
        )

    return qs


def _opcoes_filtro():
    anos = list(
        AtaRegistroPreco.objects.filter(num_ano__isnull=False)
        .values_list('num_ano', flat=True)
        .distinct()
        .order_by('-num_ano')
    )
    uasgs = list(
        AtaRegistroPreco.objects.filter(cod_id_uasg_origem_compra__isnull=False)
        .values_list('cod_id_uasg_origem_compra', flat=True)
        .distinct()
        .order_by('cod_id_uasg_origem_compra')[:200]
    )
    fornecedores = list(
        AtaRegistroPreco.objects.exclude(num_cpf_cnpj_fornecedor='')
        .values_list('num_cpf_cnpj_fornecedor', flat=True)
        .distinct()
        .order_by('num_cpf_cnpj_fornecedor')[:200]
    )
    return {
        'anos': anos,
        'uasgs': uasgs,
        'fornecedores': fornecedores,
    }


def _ultima_carga():
    return CargaLog.objects.filter(ok=True).order_by('-concluida_em').first()


def _formata_moeda_br(valor):
    """Formata valor para moeda brasileira (1.234.567,89)"""
    if valor is None:
        return "0,00"
    try:
        from decimal import Decimal, InvalidOperation
        number = Decimal(str(valor))
        formatted = f"{number:,.2f}"
        return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (InvalidOperation, ValueError, TypeError):
        return str(valor)


def _coluna_para_indice(coluna):
    indice = 0
    for caractere in coluna.upper():
        indice = indice * 26 + (ord(caractere) - ord('A') + 1)
    return indice - 1


def _valor_celula_xlsx(conteudo, tipo=None):
    if '<is>' in conteudo:
        partes = _XLSX_TEXT_RE.findall(conteudo)
        return html.unescape(''.join(partes)).strip()

    m = _XLSX_VALUE_RE.search(conteudo)
    if not m:
        return ''

    valor = html.unescape(m.group(1)).strip()
    return '' if valor.lower() == 'null' else valor


def _normaliza_numero_texto(valor):
    if valor in (None, ''):
        return ''
    texto = str(valor).strip()
    try:
        from decimal import Decimal

        numero = Decimal(texto)
        if numero == numero.to_integral():
            return str(numero.quantize(Decimal('1')))
        return format(numero.normalize(), 'f').rstrip('0').rstrip('.')
    except Exception:
        return texto


@lru_cache(maxsize=1)
def _solicitacoes_resultado_xlsx(limite=200):
    caminho = Path(__file__).resolve().parents[2] / 'dados_cggac(2).xlsx'
    if not caminho.exists():
        return []

    linhas = []
    cabecalhos = []

    with zipfile.ZipFile(caminho) as arquivo_zip, arquivo_zip.open('xl/worksheets/sheet1.xml') as fluxo:
        buffer = ''
        for bloco in iter(lambda: fluxo.read(1024 * 1024), b''):
            buffer += bloco.decode('utf-8', errors='replace')
            ultimo_fim = 0

            for match in _XLSX_ROW_RE.finditer(buffer):
                ultimo_fim = match.end()
                numero_linha = int(match.group(1))
                conteudo_linha = match.group(2)

                if numero_linha == 1:
                    cabecalhos = []
                    for celula in _XLSX_CELL_RE.finditer(conteudo_linha):
                        cabecalhos.append(_valor_celula_xlsx(celula.group(3), celula.group(2)).strip().lower())
                    continue

                if not cabecalhos:
                    continue

                registro = {}
                for celula in _XLSX_CELL_RE.finditer(conteudo_linha):
                    coluna = celula.group(1)
                    indice = _coluna_para_indice(coluna)
                    if indice >= len(cabecalhos):
                        continue
                    chave = cabecalhos[indice]
                    valor = _valor_celula_xlsx(celula.group(3), celula.group(2))
                    if chave in {
                        'qtd_solicitada',
                        'qtd_aprovada',
                        'vlr_unitario_fornecedor',
                        'qtd_maximo_adesao_compra_item',
                        'cod_id_municipio',
                        'srk_compra_item',
                        'nom_uasg_resumido',
                    }:
                        valor = _normaliza_numero_texto(valor)
                    registro[chave] = valor

                linhas.append(registro)
                if len(linhas) >= limite:
                    return linhas

            buffer = buffer[ultimo_fim:]

    return linhas


def _filtrar_solicitacoes_resultado(rows, qs, request):
    """Aplica filtros próprios da Visão Solicitações por Item (dados_cggac(2))."""
    del qs  # filtro desta visão não depende do dataset ARP

    uasg_filtro = (request.GET.get('nom_uasg_resumido') or '').strip()
    esfera_filtro = (request.GET.get('esfera') or '').strip().lower()
    poder_filtro = (request.GET.get('poder') or '').strip().lower()
    busca_filtro = (request.GET.get('q') or '').strip().lower()

    saida = []
    for row in rows:
        if uasg_filtro and str(row.get('nom_uasg_resumido', '')).strip() != uasg_filtro:
            continue

        if esfera_filtro and str(row.get('nom_esfera', '')).strip().lower() != esfera_filtro:
            continue

        if poder_filtro and str(row.get('nom_poder', '')).strip().lower() != poder_filtro:
            continue

        if busca_filtro:
            descricao = str(row.get('dsc_detalhada', '')).lower()
            nome_uasg = str(row.get('nom_uasg', '')).lower()
            nome_uasg_resumido = str(row.get('nom_uasg_resumido', '')).lower()
            if busca_filtro not in descricao and busca_filtro not in nome_uasg and busca_filtro not in nome_uasg_resumido:
                continue

        saida.append(row)

    return saida


def _opcoes_filtro_solicitacoes(rows):
    def valores_distintos(campo):
        return sorted(
            {
                str(r.get(campo, '')).strip()
                for r in rows
                if str(r.get(campo, '')).strip()
            }
        )

    return {
        'uasgs': valores_distintos('nom_uasg_resumido')[:300],
        'esferas': valores_distintos('nom_esfera'),
        'poderes': valores_distintos('nom_poder'),
    }


def _paginacao_solicitacoes_xlsx2(request, rows):
    page = _to_int(request.GET.get('page2')) or 1
    if page < 1:
        page = 1

    total = len(rows)
    page_size = _SOLICITACOES_XLSX2_PAGE_SIZE
    total_pages = max((total + page_size - 1) // page_size, 1)
    if page > total_pages:
        page = total_pages

    start = (page - 1) * page_size
    end = start + page_size
    page_rows = rows[start:end]

    params = request.GET.copy()
    if 'page2' in params:
        del params['page2']

    def _qs_for_page(target_page):
        target = params.copy()
        target['page2'] = str(target_page)
        return urlencode(target, doseq=True)

    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    page_links = [
        {
            'num': n,
            'is_current': n == page,
            'qs': _qs_for_page(n),
        }
        for n in range(start_page, end_page + 1)
    ]

    return {
        'rows': page_rows,
        'total': total,
        'page': page,
        'total_pages': total_pages,
        'page_links': page_links,
        'has_previous': page > 1,
        'has_next': page < total_pages,
        'prev_qs': _qs_for_page(page - 1) if page > 1 else '',
        'next_qs': _qs_for_page(page + 1) if page < total_pages else '',
        'start_index': start + 1 if total > 0 else 0,
        'end_index': min(end, total),
    }


def executivo(request):
    qs = _filtros_base(request)
    hoje = timezone.now().date()

    total_registros = qs.count()

    base_atas = qs.exclude(num_controle_pncp='')
    atas_distintas = base_atas.values('num_controle_pncp').distinct().count()

    carona_atas = base_atas.filter(ind_permite_carona=True).values('num_controle_pncp').distinct().count()

    vigentes = qs.filter(
        dth_vigencia_inicial_arp__isnull=False,
        dth_vigencia_final_arp__isnull=False,
        dth_vigencia_inicial_arp__lte=hoje,
        dth_vigencia_final_arp__gte=hoje,
    ).values('num_controle_pncp').distinct().count()

    vencidas = qs.filter(
        dth_vigencia_final_arp__isnull=False,
        dth_vigencia_final_arp__lt=hoje,
    ).values('num_controle_pncp').distinct().count()

    expiram_30 = qs.filter(
        dth_vigencia_final_arp__isnull=False,
        dth_vigencia_final_arp__gte=hoje,
        dth_vigencia_final_arp__lte=hoje + timedelta(days=30),
    ).values('num_controle_pncp').distinct().count()

    valor_total = qs.aggregate(total=Sum('vlr_total_arp'))['total'] or 0
    valor_medio = qs.aggregate(media=Avg('vlr_total_arp'))['media'] or 0

    por_ano = list(
        qs.filter(num_ano__isnull=False)
        .values('num_ano')
        .annotate(atas=Count('num_controle_pncp', distinct=True), valor=Sum('vlr_total_arp'))
        .order_by('num_ano')
    )

    por_uasg = list(
        qs.filter(cod_id_uasg_origem_compra__isnull=False)
        .values('cod_id_uasg_origem_compra')
        .annotate(total=Count('id'), valor=Sum('vlr_total_arp'))
        .order_by('-total')[:10]
    )

    por_fornecedor = list(
        qs.exclude(num_cpf_cnpj_fornecedor='')
        .values('num_cpf_cnpj_fornecedor')
        .annotate(total=Count('id'), valor=Sum('vlr_negociado_fornecedor'))
        .order_by('-total')[:10]
    )

    status_vigencia = {
        'vigentes': vigentes,
        'expiram_30': expiram_30,
        'vencidas': vencidas,
    }

    context = {
        'titulo': 'Atas de Registro de Preco',
        'subtitulo': 'Panorama de ARP, vigencia, carona e distribuicao por orgao/fornecedor',
        'kpis': {
            'total_registros': total_registros,
            'atas_distintas': atas_distintas,
            'carona_atas': carona_atas,
            'vigentes': vigentes,
            'vencidas': vencidas,
            'expiram_30': expiram_30,
            'valor_total': valor_total,
            'valor_medio': valor_medio,
        },
        'por_ano': por_ano,
        'por_uasg': por_uasg,
        'por_fornecedor': por_fornecedor,
        'status_vigencia': status_vigencia,
        'ultima_carga': _ultima_carga(),
        'filtros': _opcoes_filtro(),
        'get': request.GET,
    }
    return render(request, 'dashboards/executivo.html', context)


def operacional(request):
    qs = _filtros_base(request)
    hoje = timezone.now().date()

    sem_vigencia = qs.filter(Q(dth_vigencia_inicial_arp__isnull=True) | Q(dth_vigencia_final_arp__isnull=True)).count()
    sem_fornecedor = qs.filter(num_cpf_cnpj_fornecedor='').count()
    sem_uasg = qs.filter(cod_id_uasg_origem_compra__isnull=True).count()

    top_objetos = list(
        qs.exclude(dsc_objeto_arp='')
        .values('dsc_objeto_arp')
        .annotate(total=Count('id'))
        .order_by('-total')[:15]
    )

    por_uasg = list(
        qs.filter(cod_id_uasg_origem_compra__isnull=False)
        .values('cod_id_uasg_origem_compra')
        .annotate(
            total=Count('id'),
            carona=Count('id', filter=Q(ind_permite_carona=True)),
            valor=Sum('vlr_total_arp'),
        )
        .order_by('-total')[:20]
    )

    for item in por_uasg:
        total = item['total'] or 0
        carona = item['carona'] or 0
        item['pct_carona'] = round((carona / total) * 100, 1) if total else 0

    por_fornecedor = list(
        qs.exclude(num_cpf_cnpj_fornecedor='')
        .values('num_cpf_cnpj_fornecedor')
        .annotate(
            total=Count('id'),
            valor_negociado=Sum('vlr_negociado_fornecedor'),
            qtd_empenhada=Sum('qtd_empenhada_fornecedor'),
        )
        .order_by('-total')[:20]
    )

    proximas_vencer = list(
        qs.filter(
            dth_vigencia_final_arp__isnull=False,
            dth_vigencia_final_arp__gte=hoje,
        )
        .order_by('dth_vigencia_final_arp')[:50]
    )

    vencidas = list(
        qs.filter(
            dth_vigencia_final_arp__isnull=False,
            dth_vigencia_final_arp__lt=hoje,
        )
        .order_by('-dth_vigencia_final_arp')[:20]
    )

    for ata in proximas_vencer:
        ata.dias_restantes = (ata.dth_vigencia_final_arp - hoje).days

    for ata in vencidas:
        ata.dias_apos_vencimento = (hoje - ata.dth_vigencia_final_arp).days

    context = {
        'titulo': 'Atas de Registro de Preco - Operação',
        'subtitulo': 'Monitoramento tatico de vigencia, adesao e distribuicao operacional',
        'alertas': {
            'sem_vigencia': sem_vigencia,
            'sem_fornecedor': sem_fornecedor,
            'sem_uasg': sem_uasg,
            'vencidas_total': len(vencidas),
        },
        'top_objetos': top_objetos,
        'por_uasg': por_uasg,
        'por_fornecedor': por_fornecedor,
        'proximas_vencer': proximas_vencer,
        'vencidas': vencidas,
        'ultima_carga': _ultima_carga(),
        'filtros': _opcoes_filtro(),
        'get': request.GET,
    }
    return render(request, 'dashboards/operacional.html', context)


def solicitacoes_item(request):
    qs = _filtros_base(request)

    solicitacoes_resultado = _solicitacoes_resultado_xlsx(_SOLICITACOES_XLSX2_MAX_ROWS)
    solicitacoes_resultado = _filtrar_solicitacoes_resultado(solicitacoes_resultado, qs, request)
    paginacao_xlsx2 = _paginacao_solicitacoes_xlsx2(request, solicitacoes_resultado)
    filtros_solicitacoes = _opcoes_filtro_solicitacoes(_solicitacoes_resultado_xlsx(_SOLICITACOES_XLSX2_MAX_ROWS))

    context = {
        'titulo': 'Solicitacoes por Item',
        'subtitulo': 'Dados da planilha dados_cggac(2) para solicitacoes por item',
        'solicitacoes_resultado': paginacao_xlsx2['rows'],
        'solicitacoes_resultado_total': paginacao_xlsx2['total'],
        'solicitacoes_resultado_page': paginacao_xlsx2['page'],
        'solicitacoes_resultado_total_pages': paginacao_xlsx2['total_pages'],
        'solicitacoes_resultado_page_links': paginacao_xlsx2['page_links'],
        'solicitacoes_resultado_has_previous': paginacao_xlsx2['has_previous'],
        'solicitacoes_resultado_has_next': paginacao_xlsx2['has_next'],
        'solicitacoes_resultado_prev_qs': paginacao_xlsx2['prev_qs'],
        'solicitacoes_resultado_next_qs': paginacao_xlsx2['next_qs'],
        'solicitacoes_resultado_start_index': paginacao_xlsx2['start_index'],
        'solicitacoes_resultado_end_index': paginacao_xlsx2['end_index'],
        'ultima_carga': _ultima_carga(),
        'filtros_solicitacoes': filtros_solicitacoes,
        'get': request.GET,
    }
    return render(request, 'dashboards/solicitacoes_item.html', context)


def executivo_api(request):
    """API endpoint para Visão Executiva (retorna JSON para AJAX)"""
    qs = _filtros_base(request)
    hoje = timezone.now().date()

    total_registros = qs.count()
    base_atas = qs.exclude(num_controle_pncp='')
    atas_distintas = base_atas.values('num_controle_pncp').distinct().count()
    carona_atas = base_atas.filter(ind_permite_carona=True).values('num_controle_pncp').distinct().count()

    vigentes = qs.filter(
        dth_vigencia_inicial_arp__isnull=False,
        dth_vigencia_final_arp__isnull=False,
        dth_vigencia_inicial_arp__lte=hoje,
        dth_vigencia_final_arp__gte=hoje,
    ).values('num_controle_pncp').distinct().count()

    vencidas = qs.filter(
        dth_vigencia_final_arp__isnull=False,
        dth_vigencia_final_arp__lt=hoje,
    ).values('num_controle_pncp').distinct().count()

    expiram_30 = qs.filter(
        dth_vigencia_final_arp__isnull=False,
        dth_vigencia_final_arp__gte=hoje,
        dth_vigencia_final_arp__lte=hoje + timedelta(days=30),
    ).values('num_controle_pncp').distinct().count()

    valor_total = qs.aggregate(total=Sum('vlr_total_arp'))['total'] or 0
    valor_medio = qs.aggregate(media=Avg('vlr_total_arp'))['media'] or 0

    por_ano = list(
        qs.filter(num_ano__isnull=False)
        .values('num_ano')
        .annotate(atas=Count('num_controle_pncp', distinct=True), valor=Sum('vlr_total_arp'))
        .order_by('num_ano')
    )

    por_uasg = list(
        qs.filter(cod_id_uasg_origem_compra__isnull=False)
        .values('cod_id_uasg_origem_compra')
        .annotate(total=Count('id'), valor=Sum('vlr_total_arp'))
        .order_by('-total')[:10]
    )

    por_fornecedor = list(
        qs.exclude(num_cpf_cnpj_fornecedor='')
        .values('num_cpf_cnpj_fornecedor')
        .annotate(total=Count('id'), valor=Sum('vlr_negociado_fornecedor'))
        .order_by('-total')[:10]
    )

    status_vigencia = {
        'vigentes': vigentes,
        'expiram_30': expiram_30,
        'vencidas': vencidas,
    }

    # Formatar fornecedores com moeda
    for f in por_fornecedor:
        f['valor_formatado'] = _formata_moeda_br(f['valor'])

    return JsonResponse({
        'kpis': {
            'total_registros': total_registros,
            'atas_distintas': atas_distintas,
            'carona_atas': carona_atas,
            'vigentes': vigentes,
            'vencidas': vencidas,
            'expiram_30': expiram_30,
            'valor_total': _formata_moeda_br(valor_total),
            'valor_medio': _formata_moeda_br(valor_medio),
        },
        'por_ano': por_ano,
        'por_uasg': por_uasg,
        'por_fornecedor': por_fornecedor,
        'status_vigencia': status_vigencia,
    })


def operacional_api(request):
    """API endpoint para Visão Operacional (retorna JSON para AJAX)"""
    qs = _filtros_base(request)
    hoje = timezone.now().date()

    sem_vigencia = qs.filter(Q(dth_vigencia_inicial_arp__isnull=True) | Q(dth_vigencia_final_arp__isnull=True)).count()
    sem_fornecedor = qs.filter(num_cpf_cnpj_fornecedor='').count()
    sem_uasg = qs.filter(cod_id_uasg_origem_compra__isnull=True).count()

    top_objetos = list(
        qs.exclude(dsc_objeto_arp='')
        .values('dsc_objeto_arp')
        .annotate(total=Count('id'))
        .order_by('-total')[:15]
    )

    por_uasg = list(
        qs.filter(cod_id_uasg_origem_compra__isnull=False)
        .values('cod_id_uasg_origem_compra')
        .annotate(
            total=Count('id'),
            carona=Count('id', filter=Q(ind_permite_carona=True)),
            valor=Sum('vlr_total_arp'),
        )
        .order_by('-total')[:20]
    )

    for item in por_uasg:
        total = item['total'] or 0
        carona = item['carona'] or 0
        item['pct_carona'] = round((carona / total) * 100, 1) if total else 0

    por_fornecedor = list(
        qs.exclude(num_cpf_cnpj_fornecedor='')
        .values('num_cpf_cnpj_fornecedor')
        .annotate(
            total=Count('id'),
            valor_negociado=Sum('vlr_negociado_fornecedor'),
            qtd_empenhada=Sum('qtd_empenhada_fornecedor'),
        )
        .order_by('-total')[:20]
    )

    # Formatar fornecedores com moeda
    for f in por_fornecedor:
        f['valor_negociado_formatado'] = _formata_moeda_br(f['valor_negociado'])

    proximas_vencer = list(
        qs.filter(
            dth_vigencia_final_arp__isnull=False,
            dth_vigencia_final_arp__gte=hoje,
        )
        .order_by('dth_vigencia_final_arp')[:50]
        .values('num_controle_pncp', 'num_arp', 'num_ano', 'dsc_detalhada', 'dth_vigencia_final_arp')
    )

    vencidas = list(
        qs.filter(
            dth_vigencia_final_arp__isnull=False,
            dth_vigencia_final_arp__lt=hoje,
        )
        .order_by('-dth_vigencia_final_arp')[:20]
        .values('num_controle_pncp', 'num_arp', 'num_ano', 'dsc_detalhada', 'dth_vigencia_final_arp')
    )

    for ata in proximas_vencer:
        ata['dias_restantes'] = (ata['dth_vigencia_final_arp'] - hoje).days
        ata['dth_vigencia_final_arp'] = ata['dth_vigencia_final_arp'].strftime('%d/%m/%Y')

    for ata in vencidas:
        ata['dias_apos_vencimento'] = (hoje - ata['dth_vigencia_final_arp']).days
        ata['dth_vigencia_final_arp'] = ata['dth_vigencia_final_arp'].strftime('%d/%m/%Y')

    return JsonResponse({
        'alertas': {
            'sem_vigencia': sem_vigencia,
            'sem_fornecedor': sem_fornecedor,
            'sem_uasg': sem_uasg,
            'vencidas_total': len(vencidas),
        },
        'top_objetos': top_objetos,
        'por_uasg': por_uasg,
        'por_fornecedor': por_fornecedor,
        'proximas_vencer': proximas_vencer,
        'vencidas': vencidas,
    })
