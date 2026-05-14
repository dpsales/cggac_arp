/**
 * Filtros Dinâmicos - Atualiza dashboard sem recarregar página
 */

class DashboardFiltros {
  constructor(apiUrl, chartInstances = {}) {
    this.apiUrl = apiUrl;
    this.charts = chartInstances;
    this.formFiltros = document.getElementById('formFiltros');
    this.loading = false;

    if (this.formFiltros) {
      this.init();
    }
  }

  init() {
    // Monitora mudanças nos selects
    const selects = this.formFiltros.querySelectorAll('select');
    selects.forEach(select => {
      select.addEventListener('change', () => this.aplicarFiltros());
    });

    // Cancela submit do formulário tradicional
    this.formFiltros.addEventListener('submit', (e) => {
      e.preventDefault();
      this.aplicarFiltros();
    });

    this.atualizarBadgesFiltros();
  }

  obterParametros() {
    const formData = new FormData(this.formFiltros);
    const params = new URLSearchParams(formData);
    return params.toString();
  }

  async aplicarFiltros() {
    if (this.loading) return;
    this.loading = true;

    const params = this.obterParametros();
    const url = `${this.apiUrl}?${params}`;

    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data = await response.json();
      this.atualizarPagina(data);
      this.atualizarBadgesFiltros();

      // Atualizar URL sem recarregar
      window.history.replaceState({}, '', `?${params}`);
    } catch (error) {
      console.error('Erro ao buscar dados:', error);
    } finally {
      this.loading = false;
    }
  }

  atualizarPagina(data) {
    // Override em subclasses
  }

  atualizarBadgesFiltros() {
    const badgesContainer = document.getElementById('filtrosAtivosBadges');
    if (!badgesContainer || !this.formFiltros) return;

    const filtrosAtivos = [];
    const campos = [
      { name: 'ano', label: 'Ano' },
      { name: 'uasg', label: 'UASG' },
      { name: 'fornecedor', label: 'Fornecedor' },
      { name: 'vigencia', label: 'Vigencia' },
      { name: 'carona', label: 'Carona' },
    ];

    campos.forEach((campo) => {
      const select = this.formFiltros.querySelector(`select[name="${campo.name}"]`);
      if (!select || !select.value) return;
      const textoSelecionado = select.options[select.selectedIndex]?.text || select.value;
      filtrosAtivos.push(`${campo.label}: ${textoSelecionado}`);
    });

    if (filtrosAtivos.length === 0) {
      badgesContainer.innerHTML = '<span class="filter-badge filter-badge-empty">Nenhum filtro aplicado</span>';
      return;
    }

    badgesContainer.innerHTML = filtrosAtivos
      .map((filtro) => `<span class="filter-badge">${filtro}</span>`)
      .join('');
  }
}

/**
 * Dashboard Executivo
 */
class ExecutivoDashboard extends DashboardFiltros {
  atualizarPagina(data) {
    // KPIs
    document.getElementById('kpiTotalRegistros').textContent = data.kpis.total_registros;
    document.getElementById('kpiAtasDistintas').textContent = data.kpis.atas_distintas;
    document.getElementById('kpiCaronaAtas').textContent = data.kpis.carona_atas;
    document.getElementById('kpiVigentes').textContent = data.kpis.vigentes;
    document.getElementById('kpiVencidas').textContent = data.kpis.vencidas;
    document.getElementById('kpiExpiram30').textContent = data.kpis.expiram_30;
    document.getElementById('kpiValorTotal').textContent = 'R$ ' + data.kpis.valor_total;
    document.getElementById('kpiValorMedio').textContent = 'R$ ' + data.kpis.valor_medio;

    // Status Vigência (Doughnut)
    if (this.charts.chartStatus) {
      this.charts.chartStatus.data.datasets[0].data = [
        data.status_vigencia.vigentes,
        data.status_vigencia.expiram_30,
        data.status_vigencia.vencidas,
      ];
      this.charts.chartStatus.update();
    }

    // Por Ano (Bar)
    if (this.charts.chartAno && data.por_ano.length > 0) {
      const anos = data.por_ano.map(item => item.num_ano);
      const atas = data.por_ano.map(item => item.atas);
      this.charts.chartAno.data.labels = anos;
      this.charts.chartAno.data.datasets[0].data = atas;
      this.charts.chartAno.update();
    }

    // Por UASG (Horizontal Bar)
    if (this.charts.chartUasg && data.por_uasg.length > 0) {
      const uasgs = data.por_uasg.map(item => item.cod_id_uasg_origem_compra);
      const totais = data.por_uasg.map(item => item.total);
      this.charts.chartUasg.data.labels = uasgs;
      this.charts.chartUasg.data.datasets[0].data = totais;
      this.charts.chartUasg.update();
    }

    // Tabela de Fornecedores
    this.atualizarTabelaFornecedores(data.por_fornecedor);
  }

  atualizarTabelaFornecedores(fornecedores) {
    const tbody = document.querySelector('#tabelaFornecedores tbody');
    if (!tbody) return;

    if (fornecedores.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Sem dados</td></tr>';
      return;
    }

    tbody.innerHTML = fornecedores.map(f => `
      <tr>
        <td>${f.num_cpf_cnpj_fornecedor}</td>
        <td class="text-end">${f.total}</td>
        <td class="text-end">R$ ${f.valor_formatado}</td>
      </tr>
    `).join('');
  }
}

/**
 * Dashboard Operacional
 */
class OperacionalDashboard extends DashboardFiltros {
  atualizarPagina(data) {
    // Alertas
    document.getElementById('alertasVencidas').textContent = data.alertas.vencidas_total;
    document.getElementById('alertasSemVigencia').textContent = data.alertas.sem_vigencia;
    document.getElementById('alertasSemFornecedor').textContent = data.alertas.sem_fornecedor;

    // Tabelas
    this.atualizarTabelaUASG(data.por_uasg);
    this.atualizarTabelaFornecedores(data.por_fornecedor);
    this.atualizarTabelaProximas(data.proximas_vencer);
    this.atualizarTabelaVencidas(data.vencidas);
    this.atualizarTabelaObjetos(data.top_objetos);
  }

  atualizarTabelaUASG(uasgs) {
    const tbody = document.querySelector('#tabelaUASG tbody');
    if (!tbody) return;

    if (uasgs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Sem dados</td></tr>';
      return;
    }

    tbody.innerHTML = uasgs.map(u => `
      <tr>
        <td>${u.cod_id_uasg_origem_compra}</td>
        <td class="text-end">${u.total}</td>
        <td class="text-end">${u.carona}</td>
        <td class="text-end">${u.pct_carona}%</td>
      </tr>
    `).join('');
  }

  atualizarTabelaFornecedores(fornecedores) {
    const tbody = document.querySelector('#tabelaFornecedores tbody');
    if (!tbody) return;

    if (fornecedores.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Sem dados</td></tr>';
      return;
    }

    tbody.innerHTML = fornecedores.map(f => `
      <tr>
        <td>${f.num_cpf_cnpj_fornecedor}</td>
        <td class="text-end">${f.total}</td>
        <td class="text-end">R$ ${f.valor_negociado_formatado}</td>
      </tr>
    `).join('');
  }

  atualizarTabelaProximas(atas) {
    const tbody = document.querySelector('#tabelaProximas tbody');
    if (!tbody) return;

    if (atas.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Sem dados</td></tr>';
      return;
    }

    tbody.innerHTML = atas.map(a => `
      <tr>
        <td class="small">${a.num_controle_pncp || '-'}</td>
        <td>${a.num_arp}/${a.num_ano}</td>
        <td class="small">${(a.dsc_detalhada || '-').substring(0, 120)}</td>
        <td>${a.dth_vigencia_final_arp}</td>
        <td class="text-end">${a.dias_restantes}</td>
      </tr>
    `).join('');
  }

  atualizarTabelaVencidas(atas) {
    const tbody = document.querySelector('#tabelaVencidas tbody');
    if (!tbody) return;

    if (atas.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Sem dados</td></tr>';
      return;
    }

    tbody.innerHTML = atas.map(a => `
      <tr>
        <td class="small">${a.num_controle_pncp || '-'}</td>
        <td>${a.num_arp}/${a.num_ano}</td>
        <td class="small">${(a.dsc_detalhada || '-').substring(0, 120)}</td>
        <td>${a.dth_vigencia_final_arp}</td>
        <td class="text-end text-danger">${a.dias_apos_vencimento}</td>
      </tr>
    `).join('');
  }

  atualizarTabelaObjetos(objetos) {
    const tbody = document.querySelector('#tabelaObjetos tbody');
    if (!tbody) return;

    if (objetos.length === 0) {
      tbody.innerHTML = '<tr><td colspan="2" class="text-center text-muted">Sem dados</td></tr>';
      return;
    }

    tbody.innerHTML = objetos.map(o => `
      <tr>
        <td class="small">${(o.dsc_objeto_arp || '').substring(0, 180)}</td>
        <td class="text-end">${o.total}</td>
      </tr>
    `).join('');
  }
}
