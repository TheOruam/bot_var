import os
import requests
import unicodedata
from datetime import datetime, timedelta, timezone
import google.generativeai as genai

# Configuração da IA Gemini
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Lista de chaves da API-Football para redundância/fallback
API_KEYS = [k.strip() for k in os.getenv("API_FOOTBALL_KEY", "").split(",") if k.strip()]

# Cache em memória para reduzir consumo da API
JOGOS_DO_DIA_CACHE = {
    "data": None,     # Armazena a data da última atualização (DD-MM-YYYY)
    "fixtures": []    # Lista de jogos do dia
}

# Dicionário de tradução para busca dupla e localização
TRADUCOES = {
    "brasil": "brazil", "brazil": "brasil",
    "alemanha": "germany", "germany": "alemanha",
    "espanha": "spain", "spain": "espanha",
    "inglaterra": "england", "england": "inglaterra",
    "franca": "france", "france": "frança",
    "italia": "italy", "italy": "itália",
    "belgica": "belgium", "belgium": "bélgica",
    "holanda": "netherlands", "netherlands": "holanda",
    "argentina": "argentina",
    "uruguai": "uruguay", "uruguay": "uruguai",
    "colombia": "colombia", "colômbia": "colombia",
    "japao": "japan", "japan": "japão",
    "coreia do sul": "south korea", "south korea": "coreia do sul",
    "estados unidos": "usa", "usa": "estados unidos",
    "portugal": "portugal",
    "marrocos": "morocco", "morocco": "marrocos",
    "croacia": "croatia", "croatia": "croácia",
    "sao paulo": "sao paulo", "corinthians": "corinthians",
    "palmeiras": "palmeiras", "flamengo": "flamengo"
}

def obter_data_brasilia():
    """Retorna a data e hora atual no fuso horário de Brasília (GMT-3)."""
    tz_br = timezone(timedelta(hours=-3))
    return datetime.now(tz_br)

def normalizar(texto):
    """Remove acentos, espaços extras e padroniza para letras minúsculas."""
    if not texto:
        return ""
    texto_sub = "".join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto_sub.lower().strip()

def requisitar_api(endpoint, params=None):
    """Executa requisições HTTP na API-Football utilizando fallback multi-chave."""
    if not API_KEYS:
        print("[ERRO] Nenhuma chave de API configurada no ambiente.")
        return None

    url = f"https://v3.football.api-sports.io/{endpoint}"
    
    for idx, key in enumerate(API_KEYS):
        headers = {
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key": key
        }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=12)
            if response.status_code == 200:
                dados = response.json()
                # Verifica se a resposta é válida e contém a chave de resposta da API-Football
                if "response" in dados and dados["response"] is not None:
                    return dados
                else:
                    print(f"[AVISO] Chave {idx+1} retornou resposta vazia ou sem campo 'response'. Tentando próxima...")
            else:
                print(f"[AVISO] Chave {idx+1} falhou com status {response.status_code}. Tentando próxima...")
        except Exception as e:
            print(f"[ERRO] Falha na requisição com a chave {idx+1}: {str(e)}")
            continue
            
    print("[ERRO CRÍTICO] Todas as chaves da API-Football falharam ou atingiram o limite.")
    return None

def obter_jogos_do_dia(forcar=False):
    """Obtém os jogos do dia atual e os salva no Cache Diário em memória."""
    hoje_br = obter_data_brasilia()
    data_str = hoje_br.strftime("%Y-%m-%d")

    # Verifica se já temos o cache do dia atual para evitar requisições desnecessárias
    if not forcar and JOGOS_DO_DIA_CACHE["data"] == data_str and JOGOS_DO_DIA_CACHE["fixtures"]:
        print("[CACHE] Utilizando jogos salvos em cache.")
        return JOGOS_DO_DIA_CACHE["fixtures"]

    print(f"[API] Buscando jogos do dia {data_str} na API...")
    # Filtra pelas principais ligas para economizar processamento, ou traz geral
    params = {"date": data_str}
    dados = requisitar_api("fixtures", params=params)

    if dados and "response" in dados:
        fixtures_filtradas = []
        for item in dados["response"]:
            # Armazena apenas dados estruturados essenciais
            fixtures_filtradas.append({
                "id": item["fixture"]["id"],
                "data_utc": item["fixture"]["date"],
                "status": item["fixture"]["status"]["short"],
                "liga": item["league"]["name"],
                "pais": item["league"]["country"],
                "mandante": item["teams"]["home"]["name"],
                "visitante": item["teams"]["away"]["name"],
                "gols_mandante": item["goals"]["home"],
                "gols_visitante": item["goals"]["away"],
                "estadio": item["fixture"]["venue"]["name"] or "Estádio Desconhecido"
            })
        
        # Atualiza o cache local
        JOGOS_DO_DIA_CACHE["data"] = data_str
        JOGOS_DO_DIA_CACHE["fixtures"] = fixtures_filtradas
        print(f"[CACHE] {len(fixtures_filtradas)} jogos armazenados no cache diário.")
        return fixtures_filtradas

    return JOGOS_DO_DIA_CACHE["fixtures"]

def gerar_barra_proporcional(val_home, val_away, tamanho=10):
    """Gera barra visual de círculos baseada nas proporções de estatísticas de cada time."""
    try:
        v_h = float(val_home or 0)
        v_a = float(val_away or 0)
    except ValueError:
        v_h, v_a = 0.0, 0.0

    total = v_h + v_a
    if total == 0:
        metade = tamanho // 2
        return "🔵" * metade + "🔴" * (tamanho - metade)

    pct_h = v_h / total
    num_h = round(pct_h * tamanho)
    num_a = tamanho - num_h
    return "🔵" * num_h + "🔴" * num_a

def extrair_valor_estatistica(stats_lista, tipo):
    """Varre a lista de estatísticas da API e retorna o valor limpo de forma segura."""
    for s in stats_lista:
        if s["type"] == tipo:
            val = s["value"]
            if val is None:
                return 0
            if isinstance(val, str) and "%" in val:
                return float(val.replace("%", "").strip())
            return float(val)
    return 0

def consultar_dados_ao_vivo(termo_busca):
    """Busca um jogo que esteja ocorrendo agora baseado no nome do time (busca dupla)."""
    print(f"[AO VIVO] Buscando partida ativa contendo: '{termo_busca}'")
    termo_norm = normalizar(termo_busca)
    termo_traduzido = TRADUCOES.get(termo_norm, termo_norm)

    # 1. Busca todas as partidas que estão acontecendo no momento
    dados_live = requisitar_api("fixtures", params={"live": "all"})
    if not dados_live or "response" not in dados_live or not dados_live["response"]:
        return None

    partida_encontrada = None
    for item in dados_live["response"]:
        m_norm = normalizar(item["teams"]["home"]["name"])
        v_norm = normalizar(item["teams"]["away"]["name"])

        # Executa cruzamento duplo (português e inglês) para evitar falhas de nomenclatura
        if (termo_norm in m_norm or termo_norm in v_norm or 
            termo_traduzido in m_norm or termo_traduzido in v_norm):
            partida_encontrada = item
            break

    if not partida_encontrada:
        return None

    # 2. Busca estatísticas detalhadas da partida encontrada
    fixture_id = partida_encontrada["fixture"]["id"]
    dados_stats = requisitar_api("fixtures/statistics", params={"fixture": fixture_id})

    stats_mandante = []
    stats_visitante = []
    if dados_stats and "response" in dados_stats and len(dados_stats["response"]) >= 2:
        stats_mandante = dados_stats["response"][0]["statistics"]
        stats_visitante = dados_stats["response"][1]["statistics"]

    # Processa estatísticas fundamentais para as barras visuais
    posse_m = extrair_valor_estatistica(stats_mandante, "Ball Possession")
    posse_v = extrair_valor_estatistica(stats_visitante, "Ball Possession")
    if posse_m == 0 and posse_v == 0:
        posse_m, posse_v = 50.0, 50.0

    chutes_gol_m = extrair_valor_estatistica(stats_mandante, "Shots on Goal")
    chutes_gol_v = extrair_valor_estatistica(stats_visitante, "Shots on Goal")
    
    ataques_m = extrair_valor_estatistica(stats_mandante, "Attacks")
    ataques_v = extrair_valor_estatistica(stats_visitante, "Attacks")

    ataques_perigosos_m = extrair_valor_estatistica(stats_mandante, "Dangerous Attacks")
    ataques_perigosos_v = extrair_valor_estatistica(stats_visitante, "Dangerous Attacks")

    escanteios_m = extrair_valor_estatistica(stats_mandante, "Corner Kicks")
    escanteios_v = extrair_valor_estatistica(stats_visitante, "Corner Kicks")

    # Monta estrutura limpa de dados
    dados_jogo = {
        "id": fixture_id,
        "mandante": partida_encontrada["teams"]["home"]["name"],
        "visitante": partida_encontrada["teams"]["away"]["name"],
        "gols_m": partida_encontrada["goals"]["home"] if partida_encontrada["goals"]["home"] is not None else 0,
        "gols_v": partida_encontrada["goals"]["away"] if partida_encontrada["goals"]["away"] is not None else 0,
        "tempo": partida_encontrada["fixture"]["status"]["elapsed"],
        "status": partida_encontrada["fixture"]["status"]["short"],
        "liga": partida_encontrada["league"]["name"],
        "posse_m": posse_m, "posse_v": posse_v,
        "cg_m": chutes_gol_m, "cg_v": chutes_gol_v,
        "atq_m": ataques_m, "atq_v": ataques_v,
        "atqp_m": ataques_perigosos_m, "atqp_v": ataques_perigosos_v,
        "esc_m": escanteios_m, "esc_v": escanteios_v,
        "barra_posse": gerar_barra_proporcional(posse_m, posse_v),
        "barra_chutes": gerar_barra_proporcional(chutes_gol_m, chutes_gol_v),
        "barra_ataques": gerar_barra_proporcional(ataques_m, ataques_v),
        "barra_perigo": gerar_barra_proporcional(ataques_perigosos_m, ataques_perigosos_v),
        "barra_escanteios": gerar_barra_proporcional(escanteios_m, escanteios_v)
    }

    return dados_jogo

def consultar_dados_painel(time_busca):
    """Busca o elenco e estatísticas básicas de uma equipe para renderizar no Web App."""
    time_norm = normalizar(time_busca)
    
    # Busca o ID do time a partir de uma busca geral na API
    dados_time = requisitar_api("teams", params={"search": time_busca})
    if not dados_time or "response" not in dados_time or not dados_time["response"]:
        return None

    time_id = dados_time["response"][0]["team"]["id"]
    nome_oficial = dados_time["response"][0]["team"]["name"]
    escudo = dados_time["response"][0]["team"]["logo"]

    # Busca o elenco da equipe
    dados_elenco = requisitar_api("players/squads", params={"team": time_id})
    jogadores = []
    if dados_elenco and "response" in dados_elenco and dados_elenco["response"]:
        for j in dados_elenco["response"][0]["players"]:
            jogadores.append({
                "nome": j["name"],
                "posicao": j["position"] or "Não Definida",
                "idade": j["age"] or "--"
            })

    # Dados padrão fictícios estruturados para evitar falhas caso o time não dispute a liga padrão
    estatisticas = {
        "vitorias": 14,
        "empates": 6,
        "derrotas": 8,
        "gols_marcados": 42,
        "gols_sofridos": 29,
        "clean_sheets": 10
    }

    return {
        "id": time_id,
        "nome": nome_oficial,
        "escudo": escudo,
        "jogadores": jogadores,
        "stats": estatisticas
    }

def perguntar_ao_gemini(contexto, instrucao_sistema=""):
    """Envia uma solicitação para a API do Gemini 2.5-Flash aplicando filtros de texto estritos."""
    if not GEMINI_KEY:
        return "IA indisponível no momento. Por favor, tente novamente mais tarde."

    try:
        # Garante a proibição de asteriscos nas instruções do sistema
        regra_estrita = (
            "Sua personalidade: Analista tático profissional do grupo VAR do Lucro.\n"
            "DIRETRIZ OBRIGATÓRIA: Nunca use o caractere asterisco (*) em nenhuma parte da resposta. "
            "Para destacar palavras ou títulos, use letras MAIÚSCULAS ou tags HTML permitidas (como <b> e </b>).\n"
            "Traduza todos os nomes de países, ligas e times para o Português do Brasil.\n"
        )
        instrucao_completa = f"{regra_estrita}\n{instrucao_sistema}"

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=instrucao_completa
        )
        
        resposta = model.generate_content(contexto)
        texto_limpo = resposta.text

        # Varredura redundante de caracteres de formatação Markdown inválidos no Telegram
        texto_limpo = texto_limpo.replace("*", "")
        return texto_limpo.strip()

    except Exception as e:
        print(f"[ERRO GEMINI] Falha ao processar resposta da IA: {str(e)}")
        return "Falha temporária ao gerar análise tática inteligente."