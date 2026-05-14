"""
Management command: carregar_xlsx
Uso:
    python manage.py carregar_xlsx                        # usa CGGAC_XLSX_PATH do .env
    python manage.py carregar_xlsx --xlsx /caminho/arquivo.xlsx
    python manage.py carregar_xlsx --aba 0               # índice da aba (padrão: 0)
    python manage.py carregar_xlsx --limpar              # apaga todos antes de importar
"""
import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dados.models import AtaRegistroPreco, CargaLog
from dados.parser import ler_xlsx_arp

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Carrega/atualiza registros de ARP a partir do XLSX da CGGAC.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--xlsx',
            type=str,
            default=None,
            help='Caminho do arquivo XLSX. Padrão: CGGAC_XLSX_PATH em settings/env.',
        )
        parser.add_argument(
            '--aba',
            type=int,
            default=0,
            help='Índice da aba do XLSX (0 = primeira). Padrão: 0.',
        )
        parser.add_argument(
            '--limpar',
            action='store_true',
            default=False,
            help='Apaga todos os registros antes de importar.',
        )

    def handle(self, *args, **options):
        caminho = options['xlsx'] or getattr(settings, 'CGGAC_XLSX_PATH', None)
        if not caminho:
            raise CommandError(
                'Informe --xlsx ou defina CGGAC_XLSX_PATH no .env.'
            )

        caminho = Path(caminho)
        self.stdout.write(f'Lendo {caminho} …')

        log = CargaLog.objects.create(arquivo=str(caminho))

        try:
            registros, avisos = ler_xlsx_arp(caminho, aba=options['aba'])
        except Exception as exc:
            log.mensagem = f'ERRO FATAL: {exc}'
            log.ok = False
            log.concluida_em = timezone.now()
            log.save()
            raise CommandError(str(exc)) from exc

        log.total_linhas = len(registros)
        for av in avisos[:50]:  # limita log
            self.stdout.write(self.style.WARNING(f'  ⚠  {av}'))

        if options['limpar']:
            deleted, _ = AtaRegistroPreco.objects.all().delete()
            self.stdout.write(f'  ✓ {deleted} registros removidos antes da carga.')

            objs = []
            for d in registros:
                chave_pncp = d.get('num_controle_pncp', '').strip()
                numero_pregao = d.get('numero_pregao', '').strip()
                if not chave_pncp and not numero_pregao:
                    continue
                objs.append(AtaRegistroPreco(**d))

            AtaRegistroPreco.objects.bulk_create(objs, batch_size=1000)
            criados = len(objs)
            atualizados = 0
            erros = 0

            log.criados = criados
            log.atualizados = atualizados
            log.erros = erros
            log.ok = True
            log.concluida_em = timezone.now()
            log.mensagem = '\n'.join(avisos[:200])
            log.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f'Carga concluida: {criados} criados, {atualizados} atualizados, '
                    f'{erros} com erro de linha | Avisos de parse: {len(avisos)}'
                )
            )
            return

        criados = atualizados = erros = 0
        for d in registros:
            chave_pncp = d.get('num_controle_pncp', '').strip()
            numero_pregao = d.get('numero_pregao', '').strip()
            if not chave_pncp and not numero_pregao:
                continue
            try:
                lookup = {
                    'num_controle_pncp': chave_pncp,
                    'item_arp': d.get('item_arp'),
                    'srk_fornecedor': d.get('srk_fornecedor'),
                }
                _, created = AtaRegistroPreco.objects.update_or_create(
                    **lookup,
                    defaults=d,
                )
                if created:
                    criados += 1
                else:
                    atualizados += 1
            except Exception as exc:
                erros += 1
                logger.warning('Erro ao salvar %s/%s: %s', chave_pncp, numero_pregao, exc)
                if erros <= 10:
                    self.stdout.write(self.style.WARNING(f'  ⚠  {chave_pncp or numero_pregao}: {exc}'))

        log.criados = criados
        log.atualizados = atualizados
        log.erros = erros
        log.ok = True
        log.concluida_em = timezone.now()
        log.mensagem = '\n'.join(avisos[:200])
        log.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Carga concluída: {criados} criados, {atualizados} atualizados, '
                f'{erros} com erro de linha | Avisos de parse: {len(avisos)}'
            )
        )
