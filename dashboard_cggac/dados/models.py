from django.db import models


class CargaLog(models.Model):
    iniciada_em = models.DateTimeField('Iniciada em', auto_now_add=True)
    concluida_em = models.DateTimeField('Concluida em', null=True, blank=True)
    arquivo = models.CharField('Arquivo carregado', max_length=500)
    total_linhas = models.IntegerField('Total de linhas lidas', default=0)
    criados = models.IntegerField('Registros criados', default=0)
    atualizados = models.IntegerField('Registros atualizados', default=0)
    erros = models.IntegerField('Linhas com erro', default=0)
    ok = models.BooleanField('Concluida sem erro fatal?', default=False)
    mensagem = models.TextField('Mensagem/Log', blank=True)

    class Meta:
        verbose_name = 'Log de Carga'
        verbose_name_plural = 'Logs de Carga'
        ordering = ['-iniciada_em']

    def __str__(self):
        status = 'OK' if self.ok else 'ERRO'
        return f'{status} - {self.arquivo}'


class Manifestacao(models.Model):
    SENSIBILIDADE_CHOICES = [
        ('Normal', 'Normal'),
        ('Denuncia', 'Denuncia'),
        ('Sensivel', 'Sensivel'),
        ('Prioritario', 'Prioritario'),
        ('', '-'),
    ]

    SITUACAO_CHOICES = [
        ('A vencer', 'A vencer'),
        ('Expira hoje', 'Expira hoje'),
        ('Vencido', 'Vencido'),
        ('Respondido', 'Respondido'),
        ('Restituido', 'Restituido'),
        ('Em analise', 'Em analise'),
        ('Prorrogado', 'Prorrogado'),
        ('', '-'),
    ]

    ENCAMINHAMENTO_CHOICES = [
        ('Respondido', 'Respondido'),
        ('Restituido', 'Restituido'),
        ('Em analise', 'Em analise'),
        ('Aguardando area', 'Aguardando area'),
        ('Prorrogado', 'Prorrogado'),
        ('', '-'),
    ]

    sistema = models.CharField('Sistema', max_length=50, default='SEI', blank=True)
    processo = models.CharField('Processo (NUP)', max_length=80, unique=True, db_index=True)
    num_ordem = models.CharField('N de Ordem', max_length=30, blank=True)
    num_sei = models.CharField('N SEI', max_length=80, blank=True)
    demanda = models.TextField('Demanda', blank=True)
    solicitacao = models.CharField('Tipo de Solicitacao', max_length=150, blank=True)
    sensibilidade = models.CharField(
        'Sensibilidade',
        max_length=50,
        choices=SENSIBILIDADE_CHOICES,
        default='Normal',
        blank=True,
    )
    anexo = models.BooleanField('Tem Anexo?', default=False)
    cadastro = models.DateField('Data de Cadastro', null=True, blank=True, db_index=True)
    prazo_area = models.DateField('Prazo Area', null=True, blank=True)
    prazo_gabin = models.DateField('Prazo Gabinete', null=True, blank=True)
    data_entrega_area = models.DateField('Data Entrega Area', null=True, blank=True)
    prorrogacao = models.BooleanField('Prorrogado?', default=False)
    prorrogacao_data = models.DateField('Data Prorrogacao', null=True, blank=True)
    fora_do_prazo = models.BooleanField('Fora do Prazo?', default=False)
    situacao = models.CharField('Situacao', max_length=50, choices=SITUACAO_CHOICES, blank=True)
    encaminhamento = models.CharField('Encaminhamento', max_length=50, choices=ENCAMINHAMENTO_CHOICES, blank=True)
    fase_recursal = models.CharField('Fase Recursal', max_length=100, blank=True)
    ponto_focal = models.CharField('Ponto Focal', max_length=150, blank=True)
    area = models.CharField('Area', max_length=150, blank=True, db_index=True)
    subarea = models.CharField('Subarea', max_length=250, blank=True, db_index=True)
    responsavel_gabin = models.CharField('Responsavel GABIN', max_length=150, blank=True, db_index=True)
    tecnico_area = models.CharField('Tecnico Area', max_length=200, blank=True)
    catalogacao_ia = models.CharField('Catalogacao IA', max_length=150, blank=True)
    subcatalogacao = models.CharField('SubCatalogacao', max_length=250, blank=True)
    relato_demanda_ia = models.TextField('Relato Demanda (IA)', blank=True)
    relato_resposta_ia = models.TextField('Relato Resposta (IA)', blank=True)
    data_carga = models.DateTimeField('Data da Carga', auto_now=True)

    class Meta:
        verbose_name = 'Manifestacao'
        verbose_name_plural = 'Manifestacoes'
        ordering = ['-cadastro']

    def __str__(self):
        return self.processo


class AtaRegistroPreco(models.Model):
    numero_pregao = models.CharField('Numero pregao', max_length=40, blank=True, db_index=True)
    num_controle_pncp = models.CharField('Controle PNCP', max_length=80, blank=True, db_index=True)
    srk_compra = models.BigIntegerField('SRK compra', null=True, blank=True, db_index=True)
    dsc_objeto_arp = models.TextField('Objeto da ARP', blank=True)
    cod_id_uasg_origem_compra = models.BigIntegerField('UASG origem (codigo)', null=True, blank=True, db_index=True)
    num_ano = models.IntegerField('Ano', null=True, blank=True, db_index=True)
    num_arp = models.CharField('Numero ARP', max_length=40, blank=True, db_index=True)
    num_processo_compra = models.CharField('Processo compra', max_length=80, blank=True, db_index=True)

    srk_uasg_origem_compra = models.BigIntegerField('SRK UASG origem', null=True, blank=True)
    srk_orgao_compra = models.BigIntegerField('SRK orgao compra', null=True, blank=True, db_index=True)
    srk_uasg_subrrogada_compra = models.BigIntegerField('SRK UASG subrrogada', null=True, blank=True)
    srk_uasg_beneficiaria_compra = models.BigIntegerField('SRK UASG beneficiaria', null=True, blank=True)
    srk_arp_item = models.BigIntegerField('SRK ARP item', null=True, blank=True, db_index=True)
    srk_solicitacao = models.BigIntegerField('SRK solicitacao', null=True, blank=True)
    srk_solicitacao_item = models.BigIntegerField('SRK solicitacao item', null=True, blank=True)

    qtd_solicitada = models.DecimalField('Quantidade solicitada', max_digits=20, decimal_places=4, null=True, blank=True)
    qtd_aprovada = models.DecimalField('Quantidade aprovada', max_digits=20, decimal_places=4, null=True, blank=True)
    srk_uasg_solicitacao = models.BigIntegerField('SRK UASG solicitacao', null=True, blank=True)
    item_arp = models.BigIntegerField('Item ARP', null=True, blank=True)
    srk_fornecedor = models.BigIntegerField('SRK fornecedor', null=True, blank=True, db_index=True)
    srk_compra_item = models.BigIntegerField('SRK compra item', null=True, blank=True)
    srk_dominio_item_tipo_item = models.BigIntegerField('SRK tipo item', null=True, blank=True)

    qtd_homologada_vencedor_fornecedor = models.DecimalField('Qtd homologada', max_digits=20, decimal_places=4, null=True, blank=True)
    vlr_unitario_fornecedor = models.DecimalField('Valor unitario', max_digits=20, decimal_places=4, null=True, blank=True)
    vlr_negociado_fornecedor = models.DecimalField('Valor negociado', max_digits=20, decimal_places=4, null=True, blank=True)
    qtd_empenhada_fornecedor = models.DecimalField('Qtd empenhada', max_digits=20, decimal_places=4, null=True, blank=True)
    qtd_total_compra_item = models.DecimalField('Qtd total item', max_digits=20, decimal_places=4, null=True, blank=True)
    qtd_maximo_adesao_compra_item = models.DecimalField('Qtd maxima adesao', max_digits=20, decimal_places=4, null=True, blank=True)

    num_cpf_cnpj_fornecedor = models.CharField('CPF/CNPJ fornecedor', max_length=25, blank=True, db_index=True)
    dsc_detalhada = models.TextField('Descricao detalhada', blank=True)
    cod_catmatser_item = models.CharField('CATMAT/SER item', max_length=50, blank=True)

    ind_permite_carona = models.BooleanField('Permite carona', default=False, db_index=True)
    vlr_total_arp = models.DecimalField('Valor total ARP', max_digits=20, decimal_places=4, null=True, blank=True)
    dth_vigencia_inicial_arp = models.DateField('Vigencia inicial', null=True, blank=True, db_index=True)
    dth_assinatura_arp = models.DateField('Data assinatura', null=True, blank=True)
    dth_vigencia_final_arp = models.DateField('Vigencia final', null=True, blank=True, db_index=True)

    data_carga = models.DateTimeField('Data da carga', auto_now=True)

    class Meta:
        verbose_name = 'Ata de Registro de Preco'
        verbose_name_plural = 'Atas de Registro de Preco'
        ordering = ['-num_ano', 'num_arp']
        indexes = [
            models.Index(fields=['num_ano', 'num_arp']),
            models.Index(fields=['ind_permite_carona', 'num_ano']),
        ]

    def __str__(self):
        if self.num_controle_pncp:
            return self.num_controle_pncp
        return f'{self.num_arp}/{self.num_ano or ""}'
