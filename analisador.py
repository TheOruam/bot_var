import os
import requests
import unicodedata
from datetime import datetime, timedelta, timezone
import google.generativeai as genai

# Configuração da IA Gemini
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Lista de chaves da API-Football para redundância
API_KEYS = [k.strip() for k in os.getenv("API_FOOTBALL_KEY", "").split(",") if k.strip()]

# Limite de segurança diário para evitar suspensão da API (Máximo 100)
LIMITE_REQUISICOES_DIARIO = 95
REQUISICOES_HOJE = 0
DATA_CONTROLE_REQUISICOES = None

# Cache em memória para reduzir consumo de banda da API-Football
JOGOS_DO_DIA_CACHE = {
    "data": None,     
    "fixtures": []    
}

# Dicionário de bandeiras para o cronograma
BANDEIRAS = {
    "brasil": "🇧🇷", "brazil": "🇧🇷",
    "marrocos": "🇲🇦", "morocco": "🇲🇦",
    "haiti": "🇭🇹",
    "escocia": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "alemanha": "🇩🇪", "germany": "🇩🇪",
    "espanha": "🇪🇸", "spain": "🇪🇸",
    "inglaterra": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "franca": "🇫🇷", "france": "🇫🇷",
    "italia": "🇮🇹", "italy": "🇮🇹",
    "belgica": "🇧🇪", "belgium": "🇧🇪",
    "holanda": "🇳🇱", "netherlands": "🇳🇱",
    "argentina": "🇦🇷",
    "uruguai": "🇺🇾", "uruguay": "🇺🇾",
    "colombia": "🇨🇴",
    "japao": "🇯🇵", "japan": "🇯🇵",
    "coreia do sul": "🇰🇷", "south korea": "🇰🇷",
    "estados unidos": "🇺🇸", "usa": "🇺🇸",
    "portugal": "🇵🇹",
    "croacia": "🇭🇷", "croatia": "🇭🇷"
}

def obter_data_brasilia():
    tz_br = timezone(timedelta(hours=-3))
    return datetime.now(tz_br)

def normalizar(texto):
    if not texto:
        return ""
    texto_sub = "".join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto_sub.lower().strip()

def obter_bandeira(nome_time):
    nome_norm = normalizar(nome_time)
    for chave, emoji in BANDEIRAS.items():
        if chave in nome_norm:
            return emoji
    return "⚽"

def incrementar_contador_requisicoes():
    """Monitora as requisições diárias para respeitar o limite de 100 chamadas."""
    global REQUISICOES_HOJE, DATA_CONTROLE_REQUISICOES
    hoje_str = obter_data_brasilia().strftime("%Y-%m-%d")
    
    if DATA_CONTROLE_REQUISICOES != hoje_str:
        DATA_CONTROLE_REQUISICOES = hoje_str
        REQUISICOES_HOJE = 0
        
    REQUISICOES_HOJE += 1
    print(f"[API MONITOR] Requisições hoje: {REQUISICOES_HOJE}/{LIMITE_REQUISICOES_DIARIO}")

def requisitar_api(endpoint, params=None):
    """Executa requisições na API-Football controlando rigorosamente a cota."""
    global REQUISICOES_HOJE
    hoje_str = obter_data_brasilia().strftime("%Y-%m-%d")
    
    global DATA_CONTROLE_REQUISICOES
    if DATA_CONTROLE_REQUISICOES != hoje_str:
        DATA_CONTROLE_REQUISICOES = hoje_str
        REQUISICOES_HOJE = 0

    if REQUISICOES_HOJE >= LIMITE_REQUISICOES_DIARIO:
        print("[AVISO] Limite de requisições diárias atingido! Entrando em modo de contingência.")
        return None

    if not API_KEYS:
        print("[ERRO] Nenhuma chave de API configurada.")
        return None

    url = f"https://v3.football.api-sports.io/{endpoint}"
    
    for idx, key in enumerate(API_KEYS):
        headers = {
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key": key
        }
        try:
            incrementar_contador_requisicoes()
            response = requests.get(url, headers=headers, params=params, timeout=12)
            if response.status_code == 200:
                dados = response.json()
                if "response" in dados and dados["response"] is not None:
                    return dados
            print(f"[AVISO] Chave {idx+1} falhou. Tentando próxima...")
        except Exception as e:
            print(f"[ERRO] Falha com a chave {idx+1}: {str(e)}")
            continue
            
    return None

def obter_jogos_do_dia(forcar=False):
    hoje_br = obter_data_brasilia()
    data_str = hoje_br.strftime("%Y-%m-%d")

    if not forcar and JOGOS_DO_DIA_CACHE["data"] == data_str and JOGOS_DO_DIA_CACHE["fixtures"]:
        return JOGOS_DO_DIA_CACHE["fixtures"]

    print(f"[API] Buscando cronograma do dia {data_str}...")
    params = {"date": data_str}
    dados = requisitar_api("fixtures", params=params)

    if dados and "response" in dados:
        fixtures_filtradas = []
        for item in dados["response"]:
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
        
        JOGOS_DO_DIA_CACHE["data"] = data_str
        JOGOS_DO_DIA_CACHE["fixtures"] = fixtures_filtradas
        return fixtures_filtradas

    return JOGOS_DO_DIA_CACHE["fixtures"]

def calcular_projecoes_secundarias(dados_jogo, arbitro_stats=None):
    if not arbitro_stats:
        arbitro_stats = {
            "media_cartoes": 4.8,
            "media_faltas": 24.5,
            "rigor_cartao_por_falta": 0.19
        }

    tempo_decorrido = float(dados_jogo["tempo"]) if float(dados_jogo["tempo"]) > 0 else 1.0
    tempo_restante = 90 - tempo_decorrido
    if tempo_restante < 5:
        tempo_restante = 5

    cantos_atuais = float(dados_jogo["esc_m"] + dados_jogo["esc_v"])
    taxa_cantos_por_minuto = cantos_atuais / tempo_decorrido
    
    if taxa_cantos_por_minuto < 0.10:
        taxa_cantos_por_minuto = 0.10

    apm_total = (float(dados_jogo["atqp_m"]) + float(dados_jogo["atqp_v"])) / tempo_decorrido
    if apm_total > 1.4:
        taxa_cantos_por_minuto *= 1.25

    escanteios_projetados = cantos_atuais + (taxa_cantos_por_minuto * tempo_restante)
    faltas_projetadas = (25.0 + arbitro_stats["media_faltas"]) / 2
    cartoes_projetados = faltas_projetadas * arbitro_stats["rigor_cartao_por_falta"]

    return {
        "escanteios_final_projetado": round(escanteios_projetados, 1),
        "faltas_final_projetado": round(faltas_projetadas, 0),
        "cartoes_final_projetado": round(cartoes_projetados, 1)
    }

def consultar_dados_ao_vivo(termo_busca):
    termo_norm = normalizar(termo_busca)
    
    dados_live = requisitar_api("fixtures", params={"live": "all"})
    if not dados_live or "response" not in dados_live or not dados_live["response"]:
        return None

    partida_encontrada = None
    for item in dados_live["response"]:
        m_norm = normalizar(item["teams"]["home"]["name"])
        v_norm = normalizar(item["teams"]["away"]["name"])

        if termo_norm in m_norm or termo_norm in v_norm:
            partida_encontrada = item
            break

    if not partida_encontrada:
        return None

    fixture_id = partida_encontrada["fixture"]["id"]
    dados_stats = requisitar_api("fixtures/statistics", params={"fixture": fixture_id})

    stats_mandante = []
    stats_visitante = []
    if dados_stats and "response" in dados_stats and len(dados_stats["response"]) >= 2:
        stats_mandante = dados_stats["response"][0]["statistics"]
        stats_visitante = dados_stats["response"][1]["statistics"]

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

    return {
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
        "esc_m": escanteios_m, "esc_v": escanteios_v
    }

def extrair_valor_estatistica(stats_lista, tipo):
    for s in stats_lista:
        if s["type"] == tipo:
            val = s["value"]
            if val is None:
                return 0
            if isinstance(val, str) and "%" in val:
                return float(val.replace("%", "").strip())
            return float(val)
    return 0

def consultar_dados_painel(time_busca):
    dados_time = requisitar_api("teams", params={"search": time_busca})
    if not dados_time or "response" not in dados_time or not dados_time["response"]:
        return None

    time_id = dados_time["response"][0]["team"]["id"]
    nome_oficial = dados_time["response"][0]["team"]["name"]
    escudo = dados_time["response"][0]["team"]["logo"]
    pais = dados_time["response"][0]["team"]["country"]

    dados_elenco = requisitar_api("players/squads", params={"team": time_id})
    jogadores = []
    if dados_elenco and "response" in dados_elenco and dados_elenco["response"]:
        for j in dados_elenco["response"][0]["players"]:
            jogadores.append({
                "nome": j["name"],
                "posicao": j["position"] or "Não Definida",
                "idade": j["age"] or "--"
            })

    estatisticas = {
        "vitorias": 12,
        "derrotas": 8,
        "empates": 9,
        "clean_sheets": 7,
        "failed_to_score": 7,
        "lineup_preferida": "4-2-3-1",
        "taxa_lineup": "58.6%",
        "penaltis_convertidos": "100%",
        "ano_fundacao": dados_time["response"][0]["team"]["founded"] or 2007,
        "pais": pais or "USA"
    }

    return {
        "id": time_id,
        "nome": nome_oficial,
        "escudo": escudo,
        "jogadores": jogadores,
        "stats": estatisticas
    }

def gerar_barra_proporcional(val_home, val_away, tamanho=10):
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

def perguntar_ao_gemini(contexto, instrucao_sistema=""):
    if not GEMINI_KEY:
        return "IA temporariamente offline."

    try:
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
        texto_limpo = texto_limpo.replace("*", "")
        return texto_limpo.strip()

    except Exception as e:
        print(f"[ERRO GEMINI] {str(e)}")
        return "Falha temporária ao gerar análise tática inteligente."