import streamlit as st
import yfinance as yf
from deep_translator import GoogleTranslator
import plotly.express as px
from streamlit_extras.metric_cards import style_metric_cards
import plotly.graph_objects as go
import talib
import pandas as pd
from datetime import datetime
import numpy as np

#=================================================================================================================================================
#===============================================FCD MINHAS FUNCOES================================================================================
#=================================================================================================================================================

def fluxo_de_caixa_livre_ultimos_12_meses(ticker):
    #Ticker da empresa
    ticker = yf.Ticker(ticker)

    #DataFrames da empresa
    df_fluxo_de_caixa = ticker.quarterly_cashflow

    #Capex
    capex = df_fluxo_de_caixa.loc['Capital Expenditure'][0:4].sum()

    #Fluxo de caixa Operacional
    FCO = df_fluxo_de_caixa.loc['Operating Cash Flow'][0:4].sum()

    #Fluxo de caixa livre
    fluxo_de_caixa_livre_ultimos_12_meses = FCO - abs(capex)

    return fluxo_de_caixa_livre_ultimos_12_meses

def projecao_fluxo_de_caixa_livre(ticker, ano, crescimento):
    #Caixa atual
    fluxo_de_caixa_atual = fluxo_de_caixa_livre_ultimos_12_meses(ticker)

    #Dicionario de Caixa projetado
    caixas_futuros = {}

    #Ano
    ano_atual = datetime.now().year

    for i in range(ano):
        caixa = round(fluxo_de_caixa_atual * (1 + crescimento), 1)
        caixas_futuros[ano_atual + i + 1] = caixa
        fluxo_de_caixa_atual = caixa

    return caixas_futuros

def rentabilidade_bolsa_ultimos_10_anos(pais):
    #Obtém os dados históricos do Ibovespa

    if pais == 'Brasileiro':
        bolsa = yf.Ticker("^BVSP")
    elif pais == 'Estrangeiro':
        bolsa = yf.Ticker('^GSPC')

    #Historico completo
    dados = bolsa.history(period='max')

    #Adiciona uma coluna para o ano
    dados['Ano'] = dados.index.year

    #Ultimos 10 anos
    ultimo_ano = dados['Ano'].max()
    ultimos_10_anos = range(ultimo_ano - 10, ultimo_ano + 1)
    dados_filtrados = dados[dados['Ano'].isin(ultimos_10_anos)]

    #Preço de abertura do primeiro dia e fechamento do último dia de cada ano
    dados_agrupados = dados_filtrados.groupby('Ano').agg(
        preco_inicial=('Open', 'first'),
        preco_final=('Close', 'last'))

    #Rentabilidade anual
    dados_agrupados['Rentabilidade (%)'] = (
        (dados_agrupados['preco_final'] - dados_agrupados['preco_inicial']) /
        dados_agrupados['preco_inicial']) * 100

    #Media dos ultimos 10 anos
    media = dados_agrupados['Rentabilidade (%)'].mean()


    return media

def wacc(ticker,  juros, ir):
    ticker = yf.Ticker(ticker)

    # WACC = Ke (E/D+E) + Kd (D/D+E) . (1- IR)
    #RF
    rf = juros

    #Calculando Ke
    try:
        beta = ticker.info['beta']
    except:
        beta = 0.05
    rm = 0.04 + (rentabilidade_bolsa_ultimos_10_anos(mercado_escolhido)/100)
    ke = rf + beta *(rm- rf)

    #Calculando Kd
    despesas_financeiras = ticker.financials.loc['Interest Expense'].iloc[0]
    D = ticker.balance_sheet.loc['Total Debt'].iloc[0]
    kd = despesas_financeiras/D

    #Patrimonio liquido
    E = ticker.balance_sheet.loc['Stockholders Equity'].iloc[0]

    #Calculando WACC
    wacc = ke*(E/(D+E)) + kd*(D/(D+E))*(1-ir)

    return wacc

def fluxo_de_caixa_descontado_ano_determinado(ticker, ano, crescimento, juros, ir):
    #Empresa
    empresa = yf.Ticker(ticker)

    #Projecao do fluxo de caixa
    fco = list(projecao_fluxo_de_caixa_livre(ticker, ano, crescimento).values())


    #WACC
    k = wacc(ticker,  juros, ir)

    #valor da empresa
    valor_total = 0
    for i in range(len(fco)):
        valor_empresa = fco[i]/(1+k)**(i+1)
        valor_total = valor_total + valor_empresa

    #valor da acao
    numero_de_acoes = empresa.info.get('sharesOutstanding')
    valor_acao = valor_total/numero_de_acoes

    return valor_total, valor_acao

def fluxo_de_caixa_descontado(ticker, crescimento, juros, ir):
    #Empresa
    empresa = yf.Ticker(ticker)

    #anos
    anos = [5,6,7,8,9,10]

    lista_valor_total = []
    lista_valor_acao = []

    for i in (anos):
        valor_total, valor_acao = fluxo_de_caixa_descontado_ano_determinado(ticker, ano=i, crescimento=crescimento, juros=juros, ir=ir)
        lista_valor_total.append(valor_total)
        lista_valor_acao.append(valor_acao)

    media_acoes = np.mean(lista_valor_acao)
    media_valor_total = np.mean(lista_valor_total)

    return media_valor_total, media_acoes

#=================================================================================================================================================
#=========================================================PAGE CONFIG=============================================================================
#=================================================================================================================================================

st.set_page_config(layout = 'wide')


#=================================================================================================================================================
# Inicializar tradução
traducao = GoogleTranslator(source='en', target='pt')

# Verificar se 'layout' já está na session_state, se não, inicializar como None
if 'layout' not in st.session_state:
    st.session_state.layout = None

def empresa(ticker_escolhido, mercado):
    if mercado == 'Brasileiro':
        ticker = [ticker_escolhido + ".SA"]
        empresa = yf.Ticker(ticker[0])
    elif mercado == 'Estrangeiro':
        empresa = yf.Ticker(ticker_escolhido)
    return empresa

def preco_atual_acao(ticker):
    historico_preco_cindo_dias = ticker.history(period="5d")["Close"]
    preco_acao_hoje = historico_preco_cindo_dias.iloc[-1]
    preco_acao_ontem = historico_preco_cindo_dias.iloc[-2]
    preco_comparativo_ontem_hoje = preco_acao_hoje - preco_acao_ontem
    return preco_acao_hoje, preco_comparativo_ontem_hoje, preco_acao_ontem

#=================================================================================================================================================
#=========================================================INICIO==================================================================================
#=================================================================================================================================================
# Input de busca do ativo
st.title('Informações sobre empresas')
col1_linha1, col2_linha1 = st.columns([3,1])
with col1_linha1:
    escolha = st.text_input('Pesquise pelo ativo:')
with col2_linha1:
    mercado_escolhido = st.radio("Mercado:", ("Brasileiro", "Estrangeiro"), key= 'input1_info_cota')

# Botão de submeter
submeter_info_cota = st.button("Submeter",key='submeter1_info_cota')

# Quando o botão é pressionado, buscar a empresa
if submeter_info_cota:
    ticker_escolhido = empresa(escolha, mercado_escolhido)

    # Armazenar o layout da empresa no session_state
    if ticker_escolhido:
        st.session_state.layout = ticker_escolhido
#=================================================================================================================================================
#============================================================APOS BOTAO===========================================================================
#=================================================================================================================================================
# Verificar se o layout está armazenado e exibir as informações
if st.session_state.layout:
    # Primeiro container com informações básicas
    with st.container(key='container_1_info_cota'):
        col1_linha2, col2_linha2 = st.columns([3,1])
        with col1_linha2:
            st.title(st.session_state.layout.info['longName'])
            st.markdown(f'Ticker: {escolha.upper()}')
        with col2_linha2:
            preco_hoje, preco_comparativo, preco_onten = preco_atual_acao(st.session_state.layout)
            variacao_percentural_diaria = ((preco_hoje - preco_onten)/preco_onten)*100
            sifra = 'R$' if mercado_escolhido == "Brasileiro" else '$'
            st.metric(label='Cotação atual', value= f'{sifra} {round(preco_hoje,2)}', delta = f' {round(preco_comparativo,2)} ({round(variacao_percentural_diaria,2)}%)')
            style_metric_cards(
                background_color="white",
                border_color="#bdc3c7",
                border_radius_px=10,
                border_left_color = False,
                box_shadow= False
            )
#=================================================================================================================================================
#======================================================INICIO DO CONTAINER========================================================================
#=================================================================================================================================================
    # Segundo container com abas
    with st.container(key='container_2_info_cota'):
        abas = st.tabs(['Descrição', 'Gráfico da Cotação', 'Indicadores', 'Análise Técnica', 'Preços Alvo'])
#=================================================================================================================================================
#========================================================PRIMEIRA ABA - TEXTO DA EMPRESA==========================================================   
#================================================================================================================================================= 
        # Aba de descrição
        with abas[0]:
            descricao = st.session_state.layout.info['longBusinessSummary']

            # Iniciar com st.session_state.Tradutor em portugues
            if 'Tradutor' not in st.session_state:
                st.session_state.Tradutor = 'portugues'
            # Botao para alterar entre portugues e ingles
            check_tradutor = st.checkbox('Traduzir', value=True, key = 'check_tradutor_info_cotas')
            # Mudanca de lingua
            if check_tradutor:
                st.session_state.Tradutor = 'portugues'
            else:
                st.session_state.Tradutor = 'ingles'
            # Se for ingles
            if st.session_state.Tradutor == 'ingles':
                st.markdown(descricao)
            
            # Se for portugues
            if st.session_state.Tradutor == 'portugues':
                descricao_traduzida = traducao.translate(descricao)
                st.markdown(descricao_traduzida)
#=================================================================================================================================================
#===================================================SEGUNDA ABA - GRAFICO DA COTACAO==============================================================
#=================================================================================================================================================
        # Aba de gráfico
        with abas[1]:
            lista_de_periodos = ['5d', '1mo', '3mo', '6mo', 'ytd', '1y', '2y', '5y', '10y', 'max']

            lista_de_texto_lista_de_periodos = ['últimos 5 dias', 'último mês', 'últimos 3 meses',
                                                'últimos 6 meses', 'acumulados no ano', 'último ano',
                                                'últimos 2 anos', 'últimos 5 anos', 'últimos 10 anos', 'período máximo ']

            # Segmented control para escolher o período
            periodo_escolhido = st.segmented_control(
                label="Escolha o Período", 
                options=lista_de_periodos, 
                key="periodo_selecao_info_cotas",
                default = lista_de_periodos[2],
            )

            # Histórico de cotação
            cotacao = st.session_state.layout.history(period=periodo_escolhido)['Close']
            cotacao_inicia_periodo = cotacao.iloc[0]
            variacao_percentural_do_periodo = ((preco_hoje - cotacao_inicia_periodo)/cotacao_inicia_periodo)*100
            variacao_real_do_periodo = preco_hoje - cotacao_inicia_periodo

            # Definir cor da linha com base na variação percentual
            cor = 'green' if variacao_percentural_do_periodo > 0 else ('red' if variacao_percentural_do_periodo < 0 else '#34495e')
            seta = "\u2191" if variacao_percentural_do_periodo > 0 else ("\u2193" if variacao_percentural_do_periodo < 0 else '-')


            texto_periodo_escolhido = lista_de_periodos.index(periodo_escolhido)



            # Texto da variacao
            st.subheader(f':{cor}[{round(variacao_real_do_periodo,2)}'
                         f'({round(variacao_percentural_do_periodo,2)}%){seta} {lista_de_texto_lista_de_periodos[texto_periodo_escolhido]}]')
            
            # Plotar gráfico
            if periodo_escolhido:
                cotacao_df = cotacao.to_frame()
                fig = px.line(cotacao_df, x=cotacao_df.index, y=cotacao_df.columns)
                
                # Alterar a cor da linha conforme o valor de delta
                fig.update_traces(line=dict(color=cor,))
                
                fig.update_layout(
                    xaxis_title="Data",
                    yaxis_title="Valor",
                    xaxis=dict(rangeslider=dict(visible=True)),
                    yaxis=dict(fixedrange=False),
                )
                st.plotly_chart(fig, use_container_width=True, key="plotly_chart_info_cota")
#=================================================================================================================================================
#===========================================TERCEIRA ABA - INDICADORES FUNCAMENTAIS===============================================================
#=================================================================================================================================================
        # Aba de "Info"
        with abas[2]:
            informacoes_da_empresa = st.session_state.layout.info

#=================================================================================================================================================
#===========================================TERCEIRA ABA - INDICADORES FUNCAMENTAIS===============================================================
#====================================================TEXTO DO HELP================================================================================
#=================================================================================================================================================


            # Textos de ajuda
            texto_p_l = ('O P/L (Preço/Lucro) avalia o valor de uma empresa em relação ao seu desempenho financeiro.'
            ' Representa a relação entre o preço atual de uma ação e o lucro por ação (LPA) da empresa.'
            ' Em alguns setores, um P/L abaixo de 10 pode ser considerado baixo, enquanto em outros setores'
            ' um P/L acima de 20 pode ser considerado normal.'
            )
            texto_p_vp = ('O P/VP corresponde ao preço de uma ação dividido pelo seu valor patrimonial,' 
            ' sendo esse o indicador que diz o quanto os investidores estão dispostos a pagar pelo patrimônio líquido'
            ' da empresa.'
            )
            texto_dividendos = ('Quanto a empresa pagou em proventos nos últimos 12 meses.'
            )
            texto_dy = ('DY = Dividend Yield, monstra o rendimento obtivo por uma ação através dos seu proventos'
            ' pagos nos últimos 12 meses '
            )
            texto_lpa = ('Lucro líquido de uma empresa dos ultimos 12 meses que corresponde a cada ação em circulação'
            )
            texto_ps = ('Mede o valor de uma empresa de acordo com a sua receita.' +
            ' Mostra quanto os investidores estão dispostos a pagar por cada dólar de receita da empresa.'
            ' Um PSR elevado pode indicar que o mercado está disposto a pagar mais, ou que a receita é insuficiente.'
            ' Já um PSR baixo pode indicar que o mercado está pouco disposto a pagar, ou que a ação está descontada.'
            )
            texto_magem_liquida = ('Mostra a percentagem de lucro de uma empresa em relação às suas receitas.'
            ' É uma métrica que indica a rentabilidade da empresa e a sua capacidade de gerar resultados positivos.'
            ' A margem líquida ideal para uma empresa varia de acordo com o setor de atuação e com a realidade de cada negócio.'
            ' Acima de 20%: Indica uma empresa altamente lucrativa, com boa eficiência na gestão de custos e forte controle financeiro.'
            ' Comum em setores de alto valor agregado, como tecnologia, produtos de luxo, farmácia, ou serviços digitais.'
            ' Entre 10% e 20%: Indica um negócio saudável em setores com margens moderadas, como bens de consumo duráveis,'
            ' serviços financeiros e manufatura especializada. Entre 5% e 10%: Considerado bom em setores altamente'
            ' competitivos ou com grande volume de vendas,'
            ' como varejo, transporte e algumas indústrias de bens de consumo. Abaixo de 5%:'
            ' Pode ser comum em setores de baixa margem, como supermercados, commodities,'
            ' e logística. Ainda assim, exige um volume de vendas muito alto e eficiência operacional para sustentar o negócio.'
            )
            texto_margem_bruta = ('Mostra a porcentagem de lucro de uma empresa em relação às suas vendas.'
            ' Ela é calculada subtraindo os custos de produção do valor das vendas.'
            ' Margem Bruta acima de 40%-50%: Indica alta eficiência na geração de lucros em relação ao custo dos produtos ou serviços.'
            ' Comum em setores de alto valor agregado, como tecnologia, luxo, software, e produtos com diferenciação significativa.'
            ' Margem Bruta entre 20%-40%: Indicativo de um negócio saudável em setores mais competitivos ou com custos médios,'
            ' como varejo especializado, bens de consumo, e algumas indústrias manufatureiras.\n Margem Bruta abaixo de 20%:'
            ' É comum em setores de commodities, alimentos básicos, varejo de volume elevado ou serviços de baixo custo.'
            ' Pode ser sustentável, desde que a empresa compense com alto volume de vendas e controle rigoroso de despesas operacionais.'
            )
            texto_margem_ebit = ('Mostra a porcentagem do lucro operacional de uma empresa em relação à sua receita líquida'
            ' Acima de 20%: Excelente margem, indicando alta eficiência operacional e controle de custos.'
            ' Comum em setores de alto valor agregado ou com vantagens competitivas significativas,'
            ' como tecnologia, software, produtos de luxo, e farmácia.'
            ' Entre 10% e 20%: Margem saudável, comum em setores que equilibram custos de operação e geração'
            ' de receita, como manufatura especializada,'
            ' energia elétrica e serviços financeiros. Entre 5% e 10%: Margem aceitável, típica de indústrias com margens'
            ' operacionais apertadas devido a alta competitividade ou custos elevados, como varejo e transporte.'
            ' Abaixo de 5%: Pode ser preocupante em alguns setores, mas aceitável em setores de volume elevado'
            ' e margens baixas, como supermercados, commodities, e logística.'
            )
            texto_margem_ebitda = ('Mostra a lucratividade operacional de uma empresa.'
            ' Ela é calculada dividindo o lucro antes de juros, impostos, depreciação e amortização (EBITDA)'
            ' pela receita líquida da empresa.'
            ' Acima de 30%: Excelente margem, comum em setores com alta eficiência operacional e custo fixo relativamente baixo.'
            ' Exemplos: tecnologia, software, produtos de luxo, e setores monopolistas ou oligopolistas.'
            ' Entre 20% e 30%: Margem muito boa, indicando uma empresa saudável em termos operacionais.'
            ' Exemplos: serviços financeiros, energia elétrica, manufatura especializada. Entre 10% e 20%:'
            ' Margem aceitável, típica de setores mais competitivos ou com custos de operação elevados.'
            ' Exemplos: varejo especializado, bens de consumo duráveis, transporte. Abaixo de 10%:'
            ' Pode ser preocupante em alguns setores, mas aceitável em indústrias de alta competição e margens apertadas.'
            ' Exemplos: supermercados, commodities, logística.'
            ' Empresas com Margem EBITDA acima de 20% são geralmente consideradas eficientes em suas operações'
            )
            texto_roic = ('ROIC (Return on Invested Capital) é um indicador financeiro que mede a rentabilidade do'
            ' capital investido em uma empresa. Avalia a eficiência e a lucratividade de uma empresa.'
            ' ROIC acima de 15%: Excelente. Indica que a empresa gera retornos significativamente acima'
            ' do custo de capital, criando valor para os acionistas. Comum em setores de alto valor'
            ' agregado, como tecnologia, produtos farmacêuticos, e marcas de luxo. ROIC entre 10% e 15%:'
            ' Bom. Sugere que a empresa é eficiente em gerar retornos, com alguma margem acima do custo de capital.'
            ' Comum em setores como manufatura, serviços financeiros e bens de consumo duráveis.'
            ' ROIC entre 5% e 10%: Aceitável, mas pode indicar que o retorno é apenas ligeiramente'
            ' superior ao custo de capital. Comum em setores mais competitivos, como varejo,'
            ' transporte e indústrias com margens apertadas. ROIC abaixo de 5%: Preocupante.'
            ' Indica que a empresa pode estar destruindo valor, já que o retorno é menor ou igual'
            ' ao custo de capital. Comum em setores de alta competição, como supermercados, commodities'
            ' e construção civil. ROIC acima de 10% é geralmente considerado bom'
            )
            texto_roe = ('Return on Equity, que em português significa Retorno sobre o Patrimônio Líquido.'
            ' É um indicador financeiro que mede a capacidade de uma empresa gerar lucro a partir'
            ' dos recursos próprios.'
            ' ROE acima de 20%: Excelente. Indica alta eficiência em gerar retorno para os acionistas e,'
            ' muitas vezes, uma vantagem competitiva no mercado. Comum em setores com alto valor agregado'
            ' ou baixa necessidade de ativos fixos, como tecnologia, produtos de luxo e software.'
            ' ROE entre 15% e 20%: Muito bom. Mostra uma empresa lucrativa e eficiente em gerar retornos'
            ' para os acionistas. Comum em setores como bens de consumo duráveis, serviços financeiros'
            ' e indústrias com margens saudáveis. ROE entre 10% e 15%: Aceitável. Indica uma empresa que'
            ' está gerando retorno razoável, mas pode enfrentar desafios como alta competitividade ou maior'
            ' necessidade de ativos. Comum em setores de varejo, transporte e manufatura. ROE abaixo de 10%:'
            ' Preocupante. Pode indicar ineficiência em gerar retorno para os acionistas ou altos custos'
            ' operacionais. Comum em setores de margens apertadas ou empresas que enfrentam dificuldades,'
            ' como supermercados, commodities e construção civil.'
            ' ROE acima de 15% é geralmente considerado bom'
            )
            texto_roa = ('Return on Asset, que em português significa Retorno sobre Ativos.'
            ' É um indicador financeiro que mede a eficiência de uma empresa em gerar lucro'
            ' a partir dos seus ativos.'
            ' ROA acima de 10%: Excelente. Indica que a empresa utiliza seus ativos de forma'
            ' muito eficiente para gerar lucros. Comum em setores com alta rentabilidade e'
            ' baixa necessidade de ativos fixos, como tecnologia, software e produtos de luxo.'
            ' ROA entre 5% e 10%: Bom. Mostra que a empresa utiliza seus ativos de maneira'
            ' razoavelmente eficiente. Comum em setores com margens moderadas e maior'
            ' intensidade de ativos, como manufatura, bens de consumo e energia. ROA entre 2% e 5%:'
            ' Aceitável. Indica uma eficiência operacional mais baixa, comum em setores com alta'
            ' dependência de ativos fixos e margens apertadas. Exemplos: varejo, transporte,'
            ' e setores industriais de capital intensivo. ROA abaixo de 2%:'
            ' Preocupante. Pode indicar ineficiência na utilização de ativos ou margens de'
            ' lucro muito pequenas. Comum em setores de alta competição ou empresas em'
            ' dificuldades, como supermercados e commodities.'
            ' ROA acima de 5% é geralmente considerado bom'
            )
            texto_ev_ebitda = ('Relaciona o valor total de uma empresa (Enterprise Value, ou EV)'
            ' com o seu lucro antes de juros, impostos, depreciação e amortização (EBITDA).'
            ' EV/EBITDA abaixo de 5: Considerado baixo, pode indicar que a empresa está'
            ' subvalorizada ou enfrentando desafios significativos. Comum em setores'
            ' maduros ou empresas em crise, mas pode ser uma oportunidade de'
            ' investimento se os fundamentos forem sólidos. EV/EBITDA entre 5 e 10:'
            ' Considerado saudável e razoável, dependendo do setor. Indica que a empresa'
            ' é valorizada de forma justa em relação à sua capacidade de geração de caixa.'
            ' EV/EBITDA acima de 10: Considerado elevado, podendo indicar que a empresa'
            ' está supervalorizada ou que os investidores têm grandes expectativas de'
            ' crescimento futuro. Comum em setores de alta inovação ou empresas com forte'
            ' potencial de expansão. EV/EBITDA acima de 20: Muito alto, geralmente associado'
            ' a empresas de crescimento acelerado, mas pode indicar uma bolha ou avaliação'
            ' excessiva. Comum em setores como tecnologia ou startups em fase inicial.'
            ' EV/EBITDA entre 5 e 10 é geralmente considerado saudável para a maioria dos setores'
            )
            texto_ev_ebit = ('Compara o valor total de uma empresa (EV) com o seu lucro operacional'
            ' (EBIT). O EV/EBIT é um indicador que ajuda a avaliar a saúde financeira de uma empresa.'
            ' EV/EBIT abaixo de 10: Considerado atrativo, pode indicar que a empresa está subvalorizada'
            ' em relação à sua capacidade de gerar lucros operacionais. Comum em setores maduros ou'
            ' empresas enfrentando incertezas, mas também pode sinalizar uma oportunidade de investimento.'
            ' EV/EBIT entre 10 e 15: Considerado saudável e razoável para a maioria dos setores.'
            ' Sugere que a empresa está sendo avaliada de forma justa em relação à sua lucratividade'
            ' operacional. EV/EBIT acima de 15: Pode indicar que a empresa está supervalorizada ou'
            ' que os investidores têm expectativas elevadas de crescimento futuro. Comum em setores'
            ' de alta inovação ou empresas com vantagens competitivas claras. EV/EBIT acima de 20:'
            ' Muito elevado, geralmente associado a empresas de crescimento acelerado ou com alta'
            ' percepção de qualidade no mercado. Comum em setores como tecnologia ou startups com'
            ' forte potencial disruptivo.'
            ' EV/EBIT entre 10 e 15 é geralmente considerado saudável para a maioria dos setores' 
            )
            texto_divida_patrimonio = ('Mede o grau de alavancagem financeira de uma empresa.'
            ' D/P abaixo de 0,5 (50%): Excelente. Indica que a empresa tem baixa alavancagem'
            ' financeira e depende principalmente de capital próprio.'
            ' Comum em empresas com alta geração de caixa, baixo risco ou aversão ao endividamento.'
            ' D/P entre 0,5 e 1,0 (50%-100%): Considerado saudável para a maioria dos setores.'
            ' Mostra que a empresa está usando dívida de maneira equilibrada em relação ao patrimônio.'
            ' Indica que a empresa tem alavancagem controlada, mas ainda aproveita o financiamento'
            ' externo para crescer. D/P entre 1,0 e 2,0 (100%-200%): Moderado. Indica que a empresa'
            ' tem um nível de endividamento significativo, mas não necessariamente preocupante.'
            ' Comum em setores que exigem grandes investimentos iniciais, como infraestrutura,'
            ' energia e transporte. D/P acima de 2,0 (200%): Preocupante. Pode indicar alto risco'
            ' financeiro, especialmente se a empresa tiver dificuldade para gerar caixa suficiente'
            ' para cobrir seus compromissos. Comum em empresas em dificuldade ou em setores'
            ' cíclicos durante momentos de crise.'
            ' Setores com D/P Baixo (< 0,5): Tecnologia (empresas de software, SaaS,'
            ' startups digitais). Bens de consumo não duráveis (empresas com alta'
            ' geração de caixa e baixa necessidade de ativos). Farmacêuticas estabelecidas.'
            ' Setores com D/P Moderado (0,5 - 1,0): Bens de consumo duráveis'
            ' (eletrodomésticos, automóveis). Serviços financeiros (bancos, seguradoras).'
            ' Saúde e educação. Setores com D/P Elevado (1,0 - 2,0 ou mais):'
            ' Infraestrutura (construção de estradas, portos). Transporte e logística.'
            ' Energia e utilities (distribuidoras de eletricidade, gás).'
            ' D/P muito baixo nem sempre é positivo: Pode indicar que a empresa não'
            ' está aproveitando oportunidades de crescimento que poderiam ser financiadas com dívida.'
            ' Avalie junto a outros indicadores: Compare o D/P com métricas como Dívida/EBITDA,'
            ' Cobertura de Juros e Fluxo de Caixa Operacional. Comparação setorial:'
            ' Sempre compare o D/P com empresas do mesmo setor, já que diferentes indústrias'
            ' têm estruturas de capital específicas.'
            )
            texto_divida_ebitda = ('Mede a capacidade de uma empresa de pagar suas dívidas com'
            ' os lucros operacionais antes de juros, impostos, depreciação e amortização.'
            ' Ele mostra quantos anos seriam necessários para a empresa quitar suas dívidas'
            ' totais, caso mantivesse o EBITDA constante.'
            ' Dívida/EBITDA abaixo de 2: Excelente. Indica que a empresa tem um nível de'
            ' endividamento baixo em relação à sua geração de caixa operacional. Comum'
            ' em empresas com forte geração de caixa e risco financeiro reduzido.'
            ' Dívida/EBITDA entre 2 e 3: Considerado saudável para a maioria dos setores.'
            ' Mostra que a empresa está utilizando dívida de forma equilibrada em relação à'
            ' sua capacidade de geração de caixa. Dívida/EBITDA entre 3 e 4:'
            ' Moderado. Indica que a empresa está mais alavancada, mas pode ser aceitável'
            ' em setores com alta previsibilidade de receitas. Comum em empresas que estão'
            ' em fase de expansão ou em setores com grandes investimentos de capital'
            ' (infraestrutura, energia, etc.). Dívida/EBITDA acima de 4:'
            ' Preocupante. Pode indicar que a empresa está excessivamente alavancada e'
            ' enfrentando dificuldades para honrar suas dívidas. Justificável apenas em'
            ' empresas de crescimento acelerado ou setores com fluxo de caixa estável e'
            ' previsível, como utilities. Dívida/EBITDA acima de 6:'
            ' Alerta crítico. Empresas com esse nível de endividamento enfrentam'
            ' alto risco financeiro, especialmente em períodos de crise econômica.'
            ' Setores com Dívida/EBITDA Baixo (< 2): Tecnologia (empresas de software'
            ' e SaaS). Farmacêuticas com produtos estabelecidos. Setores com alta'
            ' geração de caixa e baixa necessidade de ativos fixos.'
            'Setores com Dívida/EBITDA Moderado (2-3): Bens de consumo duráveis'
            ' (automóveis, eletrodomésticos). Saúde e educação. Transporte e logística.'
            ' Setores com Dívida/EBITDA Elevado (3-4 ou mais): Infraestrutura (construção de'
            ' rodovias, portos). Utilities (energia elétrica, saneamento). Empresas de telecomunicações.'
            )
            texto_ev_ativos = ('Mede quanto o mercado está atribuindo de valor a cada unidade'
            ' de ativo da empresa. Ele reflete a eficiência percebida do uso dos ativos para'
            ' gerar valor e é útil para avaliar a precificação de empresas, especialmente'
            ' em setores intensivos em capital.'
            ' EV/Ativos abaixo de 1 (menos de 100%): Pode indicar que o mercado está'
            ' avaliando a empresa como subvalorizada em relação ao valor contábil de'
            ' seus ativos. Comum em setores maduros, empresas em crise ou indústrias'
            ' com ativos de baixa qualidade ou baixa rentabilidade. EV/Ativos próximo'
            ' de 1 (cerca de 100%): Indica que o mercado está atribuindo um valor'
            ' ao negócio próximo ao valor contábil dos ativos. Pode ser visto'
            ' como saudável para setores onde os ativos físicos desempenham'
            ' um papel significativo, como manufatura ou transporte. EV/Ativos'
            ' entre 1 e 2 (100% - 200%): Considerado bom na maioria dos setores.'
            ' Sugere que os ativos estão sendo utilizados de forma eficiente para'
            ' gerar valor acima do custo contábil. Comum em empresas com boa lucratividade'
            ' e perspectivas de crescimento. EV/Ativos acima de 2 (mais de 200%):'
            ' Pode indicar que o mercado tem grandes expectativas em relação ao futuro'
            ' da empresa, valorizando-a muito acima de seus ativos físicos. Comum em'
            ' setores como tecnologia, onde os ativos intangíveis (marca, propriedade'
            ' intelectual, etc.) são mais relevantes do que os ativos físicos.'
            ' EV/Ativos entre 1 e 2 é geralmente considerado saudável na maioria dos setores'
            )
            texto_preco_ativos = ('Mede quanto os investidores estão dispostos a'
            ' pagar por cada unidade monetária de ativos da empresa e é útil para avaliar a'
            ' relação entre o valor de mercado e o tamanho dos ativos.'
            ' P/Ativos abaixo de 1: Atrativo ou preocupante: Pode indicar que o'
            ' mercado está avaliando a empresa como subvalorizada em relação ao valor contábil'
            ' dos ativos. Pode ocorrer em empresas de setores maduros, com ativos depreciados'
            ' ou em dificuldades financeiras.Requer análise detalhada, pois pode também'
            ' sinalizar problemas na eficiência ou na qualidade dos ativos. P/Ativos entre 1 e 2:'
            ' Saudável: Indica que o mercado valoriza os ativos da empresa em um nível justo ou'
            ' moderadamente acima do valor contábil. Sugere que a empresa está usando seus ativos'
            ' de forma eficiente para gerar valor. P/Ativos acima de 2: Otimista: Reflete'
            ' expectativas elevadas de crescimento futuro ou uma alta eficiência na utilização'
            ' dos ativos. Comum em setores com ativos intangíveis significativos'
            ' (tecnologia, marcas de luxo, etc.). Deve ser analisado com cautela, pois'
            ' pode sinalizar sobrevalorização.'
            )
            texto_vpa = ('Resultado da divisão do patrimônio líquido de uma empresa pelo'
            ' número total de ações emitidas. Ele representa o valor contábil de cada ação,'
            ' ou seja, quanto cada ação vale com base no patrimônio líquido registrado nos'
            ' livros da empresa.'
            ' VPA elevado: Indica que a empresa tem um grande patrimônio líquido em relação'
            ' ao número de ações emitidas. É comum em setores com alta dependência de ativos'
            ' tangíveis, como indústrias, bancos e infraestrutura. Um VPA elevado pode ser'
            ' bom se os ativos da empresa forem eficientes em gerar lucros, mas deve ser'
            ' analisado em conjunto com a rentabilidade (ROE). VPA baixo:'
            ' Reflete um menor patrimônio líquido em relação ao número de ações.'
            ' É comum em empresas de setores com poucos ativos tangíveis, como'
            ' tecnologia, serviços ou startups. Não necessariamente é ruim, especialmente'
            ' se a empresa estiver gerando altos retornos sobre o patrimônio ou tiver ativos'
            ' intangíveis relevantes.' 
            ' Setores com VPA elevado: Bancos e seguradoras: possuem grandes patrimônios'
            ' líquidos devido à natureza de suas operações. Infraestrutura e manufatura:'
            ' dependem de grandes ativos físicos. Setores com VPA baixo: Tecnologia e'
            ' serviços: dependem mais de ativos intangíveis (propriedade intelectual,'
            ' marcas, etc.). Startups: podem ter patrimônio líquido reduzido no início'
            ' de suas operações.'
            )
            texto_preco_ebitda = ('Mede o preço de mercado de uma empresa em relação'
            ' à sua geração de caixa operacional antes de juros, impostos, depreciação'
            ' e amortização. Ele é amplamente utilizado para avaliar o valor de uma'
            ' empresa, especialmente em setores onde o EBITDA é um indicador importante'
            ' da capacidade de geração de caixa.'
            ' P/EBITDA abaixo de 5: Pode indicar subvalorização ou desconfiança do mercado'
            ' em relação ao desempenho futuro da empresa. Comum em setores maduros, com'
            ' crescimento lento, ou em empresas enfrentando dificuldades financeiras. Pode'
            ' ser atrativo para investidores de valor, mas exige análise cuidadosa'
            ' para evitar armadilhas de valor (empresas baratas por motivos justificáveis).'
            ' P/EBITDA entre 5 e 10: Geralmente considerado saudável e atrativo na maioria'
            ' dos setores. Indica que a empresa está bem avaliada em relação à sua'
            ' capacidade de geração de caixa. Comum em empresas com boa rentabilidade,'
            ' mas em setores competitivos ou cíclicos. P/EBITDA entre 10 e 15:'
            ' Indica maior valorização pelo mercado, possivelmente devido a'
            ' expectativas de crescimento ou alta rentabilidade. Comum em empresas'
            ' de setores com boas margens e crescimento consistente, como tecnologia'
            ' e saúde. Pode ser considerado elevado em setores tradicionais ou'
            ' cíclicos. P/EBITDA acima de 15: Reflete grandes expectativas de'
            ' crescimento futuro ou alta confiança do mercado na qualidade da empresa.'
            ' Comum em empresas de crescimento acelerado, setores inovadores ou'
            ' aquelas com vantagens competitivas fortes. Requer cautela, pois'
            ' pode sinalizar sobrevalorização.'
            ' Setores com P/EBITDA Baixo (< 5): Commodities (mineração,'
            ' petróleo, agricultura). Indústrias cíclicas e manufatura pesada.'
            ' Empresas em dificuldades financeiras ou economias em recessão.'
            ' Setores com P/EBITDA Moderado (5 - 10): Bens de consumo duráveis.'
            ' Transporte e logística. Setores de infraestrutura. Setores com'
            ' P/EBITDA Alto (> 10): Tecnologia (software, plataformas digitais,'
            ' SaaS). Saúde e biotecnologia. Bens de consumo premium e marcas de luxo.'
            )
            texto_receita_ativos = ('Mede a eficiência com que uma empresa utiliza'
            ' seus ativos para gerar receitas. Ele é calculado dividindo a receita'
            ' líquida pelo total de ativos. Em essência, mostra quanto de receita'
            ' é gerado para cada unidade monetária de ativo.'
            ' Receita/Ativos abaixo de 0,5 (menos de 50%): Pode indicar baixa'
            ' eficiência na utilização dos ativos ou um modelo de negócios que'
            ' exige um alto volume de ativos. Comum em setores intensivos em'
            ' capital, como manufatura pesada, infraestrutura e energia. Não'
            ' necessariamente é ruim, mas a empresa deve compensar com boa margem'
            ' de lucro. Receita/Ativos entre 0,5 e 1 (50% a 100%):'
            ' Indica que a empresa está gerando entre 50 centavos e 1 real de'
            ' receita para cada 1 real investido em ativos. Considerado um desempenho'
            ' saudável na maioria dos setores. Comum em empresas industriais'
            ' e de bens de consumo. Receita/Ativos acima de 1 (mais de 100%):'
            ' Reflete alta eficiência na utilização dos ativos para gerar receita.'
            ' Comum em setores com baixa intensidade de capital, como serviços,'
            ' tecnologia e varejo. É um sinal positivo, desde que os ativos não'
            ' estejam sendo subutilizados ou depreciados excessivamente.'
            ' Setores com Receita/Ativos Baixo (< 0,5): Energia, mineração e'
            ' petróleo (alta dependência de ativos físicos). Transporte e'
            ' logística (grande necessidade de ativos como frotas e infraestrutura).'
            ' Indústrias pesadas e construção civil. Setores com Receita/Ativos'
            ' Moderado (0,5 a 1): Bens de consumo e manufatura.'
            ' Saúde e farmacêuticos. Telecomunicações e mídia.'
            ' Setores com Receita/Ativos Alto (> 1): Varejo e comércio'
            ' eletrônico. Tecnologia e serviços baseados em ativos intangíveis.'
            'Empresas de consultoria e educação.'
            )

#=================================================================================================================================================
#===========================================TERCEIRA ABA - INDICADORES FUNCAMENTAIS===============================================================
#====================================================PRIMEIRA LINHA===============================================================================
#=================================================================================================================================================

            acoes_em_circulacao = informacoes_da_empresa['impliedSharesOutstanding']
            lucro_liquido = informacoes_da_empresa['netIncomeToCommon']
            lucro_por_acao = lucro_liquido / acoes_em_circulacao

            preco_atual_da_acoe, _, _ = preco_atual_acao(st.session_state.layout)
            dolar_x_real = yf.Ticker('USDBRL=X').history(period="5d")["Close"].iloc[0]



            patrimonio_liquido = st.session_state.layout.quarterly_balance_sheet.loc['Stockholders Equity'].iloc[0] 

            nomes_empresa_brasil_dolar = ['Petróleo Brasileiro S.A. - Petrobras', 'Vale S.A.']

            if informacoes_da_empresa['longName'] in nomes_empresa_brasil_dolar:
                patrimonio_liquido  = patrimonio_liquido * dolar_x_real

            VPA = patrimonio_liquido / acoes_em_circulacao
 
            
            #P/L
            p_l = preco_atual_da_acoe / lucro_por_acao

            # P/VP
            p_vp = preco_atual_da_acoe / VPA


            #dividendos
            dividendos_pagos_ultimos_12_meses = st.session_state.layout.history(period='1y')['Dividends'].sum()

            divedend_yied = (dividendos_pagos_ultimos_12_meses / preco_atual_da_acoe)*100
            
            # Primeira Linha
            col1_aba3_linha2, col2_aba3_linha2, col3_aba3_linha2, col4_aba3_linha2 = st.columns(4)
            # P/L
            with col1_aba3_linha2:
                st.metric(label = 'P/E (P/L)',value = round(p_l,2), help = texto_p_l)
            # P/VP
            with col2_aba3_linha2:
                st.metric('Price To Book (P/VP)',round(p_vp,2), help = texto_p_vp)
            # Dividendos valor real 
            with col3_aba3_linha2:
                st.metric('Dividendos (12m)',f'{sifra}{round(dividendos_pagos_ultimos_12_meses,2)}', help = texto_dividendos)
            # DY = dividend yield 
            with col4_aba3_linha2:
                st.metric('DY',f'{round(divedend_yied,2)}%', help = texto_dy)

#=================================================================================================================================================
#===========================================TERCEIRA ABA - INDICADORES FUNCAMENTAIS===============================================================
#====================================================SEGUNDA LINHA================================================================================
#=================================================================================================================================================

            finantial_da_empresa = st.session_state.layout.quarterly_financials
            try:
                receita_total_da_empresa = finantial_da_empresa.loc['Total Revenue'].iloc[0:4].sum()
                custo_da_receita_da_empresa = abs(finantial_da_empresa.loc['Cost Of Revenue'].iloc[0:4].sum())


                if informacoes_da_empresa['longName'] in nomes_empresa_brasil_dolar:
                    receita_total_da_empresa  = receita_total_da_empresa * dolar_x_real
                    custo_da_receita_da_empresa = custo_da_receita_da_empresa * dolar_x_real

                
                margem_liquida_da_empresa = round((lucro_liquido / receita_total_da_empresa) * 100 ,2)

                margem_bruta_da_empresa = round(((receita_total_da_empresa - custo_da_receita_da_empresa)/receita_total_da_empresa) *100,2)

                capitalizacao_de_mercado = acoes_em_circulacao * preco_atual_da_acoe


                # Price to Sales Ratio (P/S)
                p_s = round(capitalizacao_de_mercado / receita_total_da_empresa,2)

            except:
                margem_liquida_da_empresa = None
                margem_bruta_da_empresa = None
                p_s = None
            


            # Segunda Linha    
            col1_aba3_linha3, col2_aba3_linha3, col3_aba3_linha3, col4_aba3_linha3 = st.columns(4)
            # Lucro por ação (LPA)
            with col1_aba3_linha3:
                st.metric('Lucro / ação (LPA)',f'{sifra}{round(lucro_por_acao,2)}', help = texto_lpa)
            # Price to Sales Ratio (P/S)
            with col2_aba3_linha3:
                st.metric('Price to Sales (P/S)', p_s, help = texto_ps)
            # Margem Líquida
            with col3_aba3_linha3:
                st.metric('Margem Líquida', f'{margem_liquida_da_empresa}%', help = texto_magem_liquida)
            # Margem Bruta
            with col4_aba3_linha3:
                st.metric('Margem Bruta', f'{margem_bruta_da_empresa}%', help = texto_margem_bruta)

#=================================================================================================================================================
#===========================================TERCEIRA ABA - INDICADORES FUNCAMENTAIS===============================================================
#====================================================TERCEIRA LINHA===============================================================================
#=================================================================================================================================================


            balanco_da_empresa = st.session_state.layout.quarterly_balance_sheet

            divida_total_empresa = balanco_da_empresa.loc['Total Debt'].iloc[0]
            caixa_da_empresa = balanco_da_empresa.loc['Cash And Cash Equivalents'].iloc[0]

            try:
                ebit_da_empresa = finantial_da_empresa.loc['Operating Income'].iloc[0:4].sum()
                ebitda_da_empresa = informacoes_da_empresa['ebitda']


                if informacoes_da_empresa['longName'] in nomes_empresa_brasil_dolar:
                    ebit_da_empresa = ebit_da_empresa * dolar_x_real
                    divida_total_empresa = divida_total_empresa * dolar_x_real
                    caixa_da_empresa = caixa_da_empresa * dolar_x_real

                margem_ebit_da_empresa = round((ebit_da_empresa / receita_total_da_empresa)*100,2)

                margem_ebitda_da_empresa = round((ebitda_da_empresa / receita_total_da_empresa) *100,2)
                nopat = ebit_da_empresa * (1 - 0.35)
                capital_investido_da_empresa = divida_total_empresa + patrimonio_liquido - caixa_da_empresa
                roic = round((nopat / capital_investido_da_empresa)*100,2)

            except:
                margem_ebit_da_empresa = None
                margem_ebitda_da_empresa = None
                roic = None
        
            roe = (lucro_liquido / patrimonio_liquido) *100


            # Terceira Linha    
            col1_aba3_linha4, col2_aba3_linha4, col3_aba3_linha4, col4_aba3_linha4 = st.columns(4)
            # Margem EBIT
            with col1_aba3_linha4:
                st.metric('Margem EBIT', f'{margem_ebit_da_empresa}%', help = texto_margem_ebit)
            # Margem EBITDA
            with col2_aba3_linha4:
                st.metric('Margem EBITDA', f'{margem_ebitda_da_empresa}%', help = texto_margem_ebitda)
            # ROIC
            with col3_aba3_linha4:
                st.metric('ROIC', f'{roic}%', help = texto_roic)
            # ROE
            with col4_aba3_linha4:
                st.metric('ROE', f'{round(roe,2)}%',help = texto_roe)

            total_de_ativos_da_empresa = balanco_da_empresa.loc['Total Assets'].iloc[0]
            valor_de_mercado_da_empresa = acoes_em_circulacao * preco_atual_da_acoe
            ev_da_empresa = valor_de_mercado_da_empresa + divida_total_empresa - caixa_da_empresa

            if informacoes_da_empresa['longName'] in nomes_empresa_brasil_dolar:
                total_de_ativos_da_empresa = total_de_ativos_da_empresa * dolar_x_real

            roa = (lucro_liquido / total_de_ativos_da_empresa) * 100

            try:
                ev_ebitda = round(ev_da_empresa / ebitda_da_empresa,2)
                ev_ebit = round(ev_da_empresa / ebit_da_empresa,2)
            except:
                ev_ebitda = None
                ev_ebit = None
            divida_sobre_patrimonio = divida_total_empresa / patrimonio_liquido

#=================================================================================================================================================
#===========================================TERCEIRA ABA - INDICADORES FUNCAMENTAIS===============================================================
#====================================================QUARTA LINHA=================================================================================
#=================================================================================================================================================

            # Quarta Linha    
            col1_aba3_linha5, col2_aba3_linha5, col3_aba3_linha5, col4_aba3_linha5 = st.columns(4)
            # ROA
            with col1_aba3_linha5:
                st.metric('ROA', f'{round(roa,2)}%', help = texto_roa)
            # EV/EBITDA
            with col2_aba3_linha5:
                st.metric('EV/EBITDA', ev_ebitda, help = texto_ev_ebitda)
            # EV/EBIT
            with col3_aba3_linha5:
                st.metric('EV/EBIT', ev_ebit, help = texto_ev_ebit)
            # Dívida / Patrimônio
            with col4_aba3_linha5:
                st.metric('Dívida / Patrimônio', round(divida_sobre_patrimonio,2), help = texto_divida_patrimonio)

#=================================================================================================================================================
#===========================================TERCEIRA ABA - INDICADORES FUNCAMENTAIS===============================================================
#====================================================QUINTA LINHA=================================================================================
#=================================================================================================================================================

            try:
                divida_sobre_ebitda = round(divida_total_empresa / ebitda_da_empresa,2)
            except:
                divida_sobre_ebitda = None
            ev_sobre_ativos = ev_da_empresa / total_de_ativos_da_empresa
            preco_sobre_ativos = valor_de_mercado_da_empresa / total_de_ativos_da_empresa

            # Quinta Linha    
            col1_aba3_linha6, col2_aba3_linha6, col3_aba3_linha6, col4_aba3_linha6 = st.columns(4)
            # Dívida / EBITDA
            with col1_aba3_linha6:
                st.metric('Dívida / EBITDA', divida_sobre_ebitda, help = texto_divida_ebitda)
            # EV / Ativos
            with col2_aba3_linha6:
                st.metric('EV / Ativos', round(ev_sobre_ativos,2), help = texto_ev_ativos)
            # Preço / Ativos
            with col3_aba3_linha6:
                st.metric('Preço / Ativos', round(preco_sobre_ativos,2), help = texto_preco_ativos)
            # VPA
            with col4_aba3_linha6:
                st.metric('VPA', f'{sifra}{round(VPA,2)}', help = texto_vpa)

#=================================================================================================================================================
#===========================================TERCEIRA ABA - INDICADORES FUNCAMENTAIS===============================================================
#====================================================SEXTA LINHA==================================================================================
#=================================================================================================================================================

            try:
                preco_sobre_ebitda = round(valor_de_mercado_da_empresa / ebit_da_empresa,2)
            except:
                preco_sobre_ebitda = None
            receita_ativos = receita_total_da_empresa / total_de_ativos_da_empresa


            # Sexta Linha    
            col1_aba3_linha7, col2_aba3_linha7, col3_aba3_linha7, col4_aba3_linha7 = st.columns(4)
            # vazio
            with col1_aba3_linha6:
                _ = ''
            # Preço / EBITDA
            with col2_aba3_linha6:
                st.metric('Preço / EBITDA', preco_sobre_ebitda, help = texto_preco_ebitda)
            # Receita / Ativos
            with col3_aba3_linha6:
                st.metric('Receita / Ativos', round(receita_ativos,2), help = texto_receita_ativos)
            # vazio
            with col4_aba3_linha6:
                _ = ''

#=================================================================================================================================================
#===========================================QUARTA ABA - ANALISE TECNICA==========================================================================
#=================================================================================================================================================

        with abas[3]:
            lista_de_periodos = ['2y', '5y', '10y', 'max']

            col1_aba4_linha1, col2_aba4_linha1= st.columns(2)
            with col1_aba4_linha1:
                periodo_da_analise = st.segmented_control(
                    label="Período", 
                    options=lista_de_periodos, 
                    key="periodo_da_analise_info_cotas",
                    default = lista_de_periodos[2],
                )

            cota_analise_tecnica = st.session_state.layout.history(period=periodo_da_analise)

            cota_grafica = st.session_state.layout.history(period=periodo_da_analise)
            

            fig = go.Figure(data = go.Candlestick(
                x = cota_analise_tecnica.index,
                open = cota_grafica['Open'],
                high = cota_grafica['High'],
                low = cota_grafica['Low'],
                close = cota_grafica['Close']
            ))
            fig.update_layout(
                xaxis=dict(title="Data", rangeslider=dict(visible=False)),
                yaxis=dict(title="Preço"),
                height=950,
                dragmode="pan"
            )





#=================================================================================================================================================
#=================================================MEDIA MOVEL=====================================================================================
#=================================================================================================================================================

            with col2_aba4_linha1:
                add_ma_pills = st.segmented_control('Média Móvel',options= ['None', 5, 10, 20, 30, 50, 100, 200],default='None', key = 'add_ma_button_info_cota')

            if type(add_ma_pills) != str:
                ma_50 = talib.SMA(cota_analise_tecnica['Close'], timeperiod=add_ma_pills)
                fig.add_trace(go.Scatter(
                    x=cota_analise_tecnica.index,
                    y=ma_50,
                    mode='lines',
                    name='Média Móvel 50'
                ))


            with st.container(height = 1000):
                st.plotly_chart(fig, key= 'plotly_chart2_info_cota', use_container_width=True)


#=================================================================================================================================================
#===========================================QUINTA ABA - PRECO ALVO===============================================================================
#=================================================================================================================================================


        with abas[4]:
            info_cota_preco_alvo = st.session_state.layout.info

            def o_que_fazer(situacao):
                if situacao == -1:
                    texto_compra = 'Compra'
                elif situacao == 0:
                    texto_compra = 'Neutro'
                elif situacao == 1:
                    texto_compra = 'Venda'
                return texto_compra
            def df_det(up, low, historico):
                det = pd.concat([up, low, historico['Close']],axis = 1, join= 'inner')
                det.columns = ['up', 'lo', 'clo']
                det['cruza'] = np.where(det['clo']>det['up'], 1,0)
                det['cruza'] = np.where(det['clo']<det['lo'], -1, det['cruza'])
                compra_det = det['cruza'].iloc[-1]
                return compra_det
            def interpretar_macd(macd, signal):
                # Sinal de Compra: MACD cruza acima do Sinal
                if macd[-1] > signal[-1] and macd[-2] <= signal[-2]:
                    return "Compra"
                # Sinal de Venda: MACD cruza abaixo do Sinal
                elif macd[-1] < signal[-1] and macd[-2] >= signal[-2]:
                    return "Venda"
                # Nenhum sinal claro
                return "Neutro"
                        
            # Preco alvo YF target
            try:
                preco_alvo_yf_target_medio = round(info_cota_preco_alvo['targetMedianPrice'],2)
                preco_alvo_yf_target_low = round(info_cota_preco_alvo['targetLowPrice'],2)
                preco_alvo_yf_target_high = round(info_cota_preco_alvo['targetHighPrice'],2)
            except:
                preco_alvo_yf_target_medio = None
                preco_alvo_yf_target_low = None
                preco_alvo_yf_target_high = None

            # Meu preco alvo
            if mercado_escolhido == 'Brasileiro':
                crescimento = 0.04
                juros = 0.1
                ir = 0.34
                escolha_preco_alvo = f'{escolha}.SA'
            elif mercado_escolhido == 'Estrangeiro':
                crescimento = 0.6
                juros = 0.035
                ir = 0.25
                escolha_preco_alvo = escolha

            try:
                _, preco_alvo_FCD = fluxo_de_caixa_descontado(ticker = escolha_preco_alvo, crescimento=crescimento, juros=juros, ir = ir)
            except:
                preco_alvo_FCD = 0

            # Compra bollinger
            #Tripla Suavizada
            historico_bollinger = st.session_state.layout.history(period = '2y')
            up_tripla_suavizada, mid_tripla_suavizada, low_tripla_suavizada = talib.BBANDS(historico_bollinger['Close'],
                                                                                            matype= talib.MA_Type.T3)
            compra_bollinger_tripla_suavizada = df_det(up_tripla_suavizada, low_tripla_suavizada, historico_bollinger)
            texto_compra_bollinger_tripla_suavizada = o_que_fazer(compra_bollinger_tripla_suavizada)

            # Curto prazo EMA 
            up_EMA, mid_EMA, low_EMA = talib.BBANDS(historico_bollinger['Close'], timeperiod=10,
                                                    nbdevup=2, nbdevdn=2, matype=talib.MA_Type.EMA)    
            compra_bollinger_EMA = df_det(up_EMA, low_EMA, historico_bollinger)
            texto_compra_bollinger_EMA = o_que_fazer(compra_bollinger_EMA)            

            # Curto prazo WMA 
            up_WMA, mid_WMA, low_WMA = talib.BBANDS(historico_bollinger['Close'], timeperiod=14,
                                                    nbdevup=2, nbdevdn=2, matype=talib.MA_Type.WMA)
            compra_bollinger_WMA = df_det(up_WMA, low_WMA, historico_bollinger)
            texto_compra_bollinger_WMA = o_que_fazer(compra_bollinger_WMA)

            # Medio prazo EMA
            up_EMA_medio, mid_EMA_medio, low_EMA_medio = talib.BBANDS(historico_bollinger['Close'], timeperiod=30,
                                                    nbdevup=2, nbdevdn=2, matype=talib.MA_Type.EMA)    
            compra_bollinger_EMA_medio = df_det(up_EMA_medio, low_EMA_medio, historico_bollinger)
            texto_compra_bollinger_EMA_medio = o_que_fazer(compra_bollinger_EMA_medio)

            # Medio prazo SMA          
            up_SMA_medio, mid_SMA_medio, low_SMA_medio = talib.BBANDS(historico_bollinger['Close'], timeperiod=20,
                                                    nbdevup=2, nbdevdn=2, matype=talib.MA_Type.SMA)
            compra_bollinger_SMA_medio = df_det(up_SMA_medio, low_SMA_medio, historico_bollinger)
            texto_compra_bollinger_SMA_medio = o_que_fazer(compra_bollinger_SMA_medio)

            # Longo prazo SMA
            up_SMA_longo, mid_SMA_longo, low_SMA_longo = talib.BBANDS(historico_bollinger['Close'], timeperiod=75,
                                                    nbdevup=2, nbdevdn=2, matype=talib.MA_Type.SMA)
            compra_bollinger_SMA_longo = df_det(up_SMA_longo, low_SMA_longo, historico_bollinger)
            texto_compra_bollinger_SMA_longo = o_que_fazer(compra_bollinger_SMA_longo)

            # Longo prazo T3   
            up_T3_longo, mid_T3_longo, low_T3_longo = talib.BBANDS(historico_bollinger['Close'], timeperiod=75,
                                                    nbdevup=2, nbdevdn=2, matype=talib.MA_Type.SMA)
            compra_bollinger_T3_longo = df_det(up_T3_longo, low_T3_longo, historico_bollinger)
            texto_compra_bollinger_T3_longo = o_que_fazer(compra_bollinger_T3_longo)

            # S&P Longo prazo
            up_SP_longo, mid_SP_longo, low_SP_longo = talib.BBANDS(historico_bollinger['Close'], timeperiod=200,
                                                    nbdevup=2, nbdevdn=2, matype=talib.MA_Type.SMA)            
            compra_bollinger_SP_medio = df_det(up_SP_longo, low_SP_longo, historico_bollinger)           
            texto_compra_bollinger_SP_longo = o_que_fazer(compra_bollinger_SP_medio)

            
            #RSI
            rsi = talib.RSI(historico_bollinger['Close'], timeperiod=14)
            rsi_hoje = rsi[-1]

            # MACD
            # Day trade
            macd_DT, macdsignal_DT, macdhist_DT = talib.MACD(historico_bollinger['Close'], fastperiod=8, slowperiod=21, signalperiod=5)
            texto_macd_DT = interpretar_macd(macd_DT, macdsignal_DT)

            # Médio Prazo
            macd_MP, macdsignal_MP, macdhist_MP= talib.MACD(historico_bollinger['Close'], fastperiod=12, slowperiod=26, signalperiod=9)
            texto_macd_MP = interpretar_macd(macd_MP, macdsignal_MP)

            # Longo prazo
            macd_LP, macdsignal_LP, macdhist_LP= talib.MACD(historico_bollinger['Close'], fastperiod=19, slowperiod=39, signalperiod=9)
            texto_macd_LP = interpretar_macd(macd_LP, macdsignal_LP)



#=================================================================================================================================================
#===========================================QUINTA ABA - PRECO ALVO===============================================================================
#===================================================TEXTOS========================================================================================
#=================================================================================================================================================
            
            help_compra_bollinger_tripla_suavizada = ('Essa média móvel é uma variante mais sofisticada,'
                                          ' projetada para suavizar os dados, reduzindo o ruído'
                                          ' de curto prazo enquanto mantém a sensibilidade às mudanças'
                                          ' de tendência. Ela aplica múltiplos níveis de suavização,'
                                          ' tornando-a menos propensa a reagir a flutuações menores no preço.'
                                          ' Como funciona: A T3 utiliza várias camadas de médias móveis exponenciais'
                                          ' (EMAs) aplicadas iterativamente, adicionando um fator de suavização adicional'
                                          ' chamado "coeficiente de suavização". Vantagens: Mais suave que a EMA ou DEMA'
                                          ' (Double Exponential Moving Average). Menor atraso do que a SMA ou outras médias'
                                          ' simples, ajudando a identificar mudanças de tendência mais rapidamente. Desvantagens:'
                                          ' Pode ser menos responsiva em mercados muito voláteis.'
                                          ' Quando usar a T3? Mercados laterais ou com ruído significativo:'
                                          ' A T3 ajuda a filtrar movimentos pequenos, evitando sinais falsos. Análise de'
                                          ' tendências de médio/longo prazo: Sua suavização adicional é ideal para detectar'
                                          ' mudanças de tendência mais confiáveis. Acompanhamento de ativos com volatilidade moderada:'
                                          ' Ativos que possuem movimentos consistentes, mas sem grandes picos de volatilidade,'
                                          ' podem se beneficiar da sensibilidade controlada da T3.'
            )
            help_compra_bollinger_EMA = ('Características: Mais responsiva às mudanças recentes de preço do que a SMA.'
                                         ' Suaviza menos o movimento, capturando rapidamente mudanças no mercado.'
                                         ' É amplamente usada em mercados voláteis e ativos que se movem rapidamente.'
                                         ' Quando usar: Curto prazo (day trade ou swing trade de poucos dias).'
                                         ' Para ativos ou índices com volatilidade elevada, como o IBOV em períodos'
                                         ' de notícias ou eventos relevantes. Quando você quer reagir rapidamente a'
                                         ' movimentos do mercado, especialmente em rompimentos.'
                                         )
            help_compra_bollinger_WMA = ('Características: Também é mais responsiva que a SMA, mas menos que a EMA'
                                         ' em alguns casos. Captura mudanças de curto prazo, mas o impacto de novos'
                                         ' preços diminui linearmente, não exponencialmente. Menos suscetível a grandes'
                                         ' flutuações causadas por um único ponto fora da curva. Quando usar:'
                                         ' Curto prazo (day trade ou swing trade). Para ativos ou índices com menor'
                                         ' volatilidade, onde movimentos extremos são menos frequentes.'
                                         ' Quando você prefere um equilíbrio entre suavidade e sensibilidade'
                                         ' (mais estável que EMA, mas mais responsiva que SMA).'
                                         )
            help_rsi = ('Acima de 70: O ativo pode estar sobrecomprado, indicando possível correção ou reversão de tendência.'
            ' Abaixo de 30: O ativo pode estar sobrevendido, indicando possível recuperação.'
            )

            


#=================================================================================================================================================
#===========================================QUINTA ABA - PRECO ALVO===============================================================================
#==================================================COLUNAS========================================================================================
#=================================================================================================================================================



            col1_aba5_linha1, col2_aba5_linha1, col3_aba5_linha1 = st.columns(3)
            with col1_aba5_linha1:
                st.metric('Preço Alvo YF  Médio', value = f'{sifra} {preco_alvo_yf_target_medio}')
            with col2_aba5_linha1:
                st.metric('Preço Alvo YF  Baixo', value = f'{sifra} {preco_alvo_yf_target_low}')
            with col3_aba5_linha1:
                st.metric('Preço Alvo YF  Alto', value = f'{sifra} {preco_alvo_yf_target_high}')
            

            col1_aba5_linha2, col2_aba5_linha2, col3_aba5_linha2 = st.columns(3)
            with col1_aba5_linha2:
                st.metric('Preço Alvo FCD', value = f'{sifra} {round(preco_alvo_FCD,2)}')


#=================================================================================================================================================
#===========================================QUINTA ABA - PRECO ALVO===============================================================================
#==============================================COLUNAS TRADING====================================================================================
#=================================================================================================================================================

            st.header('Trading')
            st.markdown('Bandas de Bollinger')    
            col1_aba5_linha3, col2_aba5_linha3, col3_aba5_linha3 = st.columns(3)
            with col1_aba5_linha3:
                st.metric('Tripla Suavizada', value = texto_compra_bollinger_tripla_suavizada, help = help_compra_bollinger_tripla_suavizada)
            with col2_aba5_linha3:
                st.metric('Curto Prazo EMA', value = texto_compra_bollinger_EMA, help = help_compra_bollinger_EMA)
            with col3_aba5_linha3:
                st.metric('Curto Prazo WMA', value = texto_compra_bollinger_WMA, help = help_compra_bollinger_WMA)

            col1_aba5_linha4, col2_aba5_linha4, col3_aba5_linha4 = st.columns(3)
            with col1_aba5_linha4:
                st.metric('Médio prazo EMA', value = texto_compra_bollinger_EMA_medio)
            with col2_aba5_linha4:
                st.metric('Médio prazo SMA', value = texto_compra_bollinger_SMA_medio)
            with col3_aba5_linha4:
                st.metric('Longo Prazo SMA', value = texto_compra_bollinger_SMA_longo)

            col1_aba5_linha5, col2_aba5_linha5, col3_aba5_linha5 = st.columns(3)
            with col1_aba5_linha5:
                st.metric('Longo Prazo T3', value = texto_compra_bollinger_T3_longo)
            with col2_aba5_linha5:
                st.metric('Longo prazo S&P', value = texto_compra_bollinger_SP_longo)

            st.markdown('RSI (Índice de Força Relativa)') 
            col1_aba5_linha6, col2_aba5_linha6, col3_aba5_linha6 = st.columns(3)
            with col1_aba5_linha6:
                st.metric('RSI', value = (round(rsi_hoje,2)), help = help_rsi)
            
            st.markdown('MACD') 
            col1_aba5_linha7, col2_aba5_linha7, col3_aba5_linha7 = st.columns(3)
            with col1_aba5_linha7:
                st.metric('MACD - Day trade', value = texto_macd_DT)
            with col2_aba5_linha7:
                st.metric('MACD - Médio Prazo', value = texto_macd_MP)
            with col3_aba5_linha7:
                st.metric('MACD - Longo prazo', value = texto_macd_LP)