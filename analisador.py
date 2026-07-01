# analisador.py
import os
import time
import requests
import random
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types
from google.genai.errors import APIError
from typing import Optional, Dict, Any, List

API_FOOTBALL_URL_DIRECT = "https://v3.football.api-sports.io"
API_FOOTBALL_URL_RAPID = "https://api-football-v1.p.rapidapi.com/v3"

# SISTEMA DE CACHE BRUTO DIÁRIO (ECONOMIA DE COTA + FILTRO DINÂMICO IMEDIATO)
LIGAS_MONITORADAS = [71, 72, 73, 1, 39, 140, 2]
JOGOS_DO_DIA_RAW_CACHE = []  # Guarda todos os jogos de hoje ajustados ao fuso de Brasília
ULTIMA_CARGA_JOGOS = ""      # Guarda a data da última requisição real (ex: "2026-06-30")
JOGOS_ANALISADOS = set()
ALERTAS_ENVIADOS = set()
ULTIMO_DIA_CRONOGRAMA = ""

def obter_cliente_gemini() -> genai.Client:
    """Inicializa de forma segura o cliente da API do Google GenAI."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chave de ambiente 'GEMINI_API_KEY' não configurada.")
    return genai.Client(api_key=api_key)

def gerar_texto_ia_local(prompt: str) -> str:
    """Gera pequenos alertas de texto usando o Gemini 2.5 Flash."""
    try:
        client = obter_cliente_gemini()
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Erro ao gerar alerta por IA local: {e}")
        return "Foco na cabine do VAR! Mais uma partida emocionante se aproxima."

# =====================================================================
# SISTEMA DE DUPLO PORTAL COM REDUNDÂNCIA (FALLBACK MULTI-CHAVE BLINDADO)
# =====================================================================

def fazer_requisicao_api(endpoint: str) -> Dict[str, Any]:
    """
    Realiza requisições para a API-Football utilizando um sistema inteligente de duplo portal.
    Tenta o portal direto (API-Sports) e o portal RapidAPI para cada chave configurada.
    """
    raw_keys = os.getenv("API_FOOTBALL_KEY", "")
    chaves = [k.strip() for k in raw_keys.split(",") if k.strip()]
    
    if not chaves:
        print("❌ [Fallback API] Erro: Nenhuma API_FOOTBALL_KEY foi configurada no Render.")
        return {"response": [], "errors": "Chave não configurada"}

    ultimo_erro = None

    for i, chave in enumerate(chaves):
        # ─── TENTATIVA 1: PORTAL DIRETO (API-SPORTS) ───
        try:
            url_direto = f"{API_FOOTBALL_URL_DIRECT}/{endpoint}"
            headers_direto = {'x-apisports-key': chave}
            
            resposta = requests.get(url_direto, headers=headers_direto, timeout=12)
            dados = resposta.json()
            
            if "response" in dados and not dados.get("errors"):
                return dados
                
            ultimo_erro = dados.get("errors") if dados.get("errors") else dados
            print(f"ℹ️ [Fallback API] Chave {i+1} falhou no portal direto. Tentando pelo portal RapidAPI...")
            
        except Exception as e:
            print(f"⚠️ [Fallback API] Erro físico com chave {i+1} no portal direto: {e}. Tentando RapidAPI...")
            ultimo_erro = str(e)

        # ─── TENTATIVA 2: PORTAL SECUNDÁRIO (RAPIDAPI) ───
        try:
            url_rapid = f"{API_FOOTBALL_URL_RAPID}/{endpoint}"
            headers_rapid = {
                'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
                'x-rapidapi-key': chave
            }
            
            resposta = requests.get(url_rapid, headers=headers_rapid, timeout=12)
            dados = resposta.json()
            
            if "response" in dados and not dados.get("errors"):
                return dados
                
            ultimo_erro = dados.get("errors") if dados.get("errors") else dados
            print(f"⚠️ [Fallback API] Chave {i+1} também falhou no portal RapidAPI. Motivo: {ultimo_erro}")
            
        except Exception as e:
            print(f"⚠️ [Fallback API] Erro físico com chave {i+1} no portal RapidAPI: {e}")
            ultimo_erro = str(e)
            
    print("❌ [Fallback API] Alerta Crítico: Todas as chaves de API e portais falharam.")
    return {"response": [], "errors": ultimo_erro}

# =====================================================================
# SEÇÃO 1: ANÁLISE PRÉ-JOGO, CRONOGRAMA E RESUMO DETALHADO COM VERIFICAÇÃO DE GREENS
# =====================================================================

def obter_jogos_do_dia() -> List[Dict[str, Any]]:
    """
    Busca as partidas de hoje e amanhã no planeta e filtra localmente baseado no 
    Horário de Brasília (UTC-3), corrigindo o 'Bug da Meia-noite' de jogos tardios.
    """
    global JOGOS_DO_DIA_RAW_CACHE, ULTIMA_CARGA_JOGOS
    
    agora_brt = datetime.now(timezone.utc) - timedelta(hours=3)
    hoje_brt = agora_brt.strftime('%Y-%m-%d')
    
    # Se já temos os jogos do dia carregados e consolidados em cache, retorna diretamente
    if hoje_brt == ULTIMA_CARGA_JOGOS and JOGOS_DO_DIA_RAW_CACHE:
        jogos_filtrados = [
            jogo for jogo in JOGOS_DO_DIA_RAW_CACHE 
            if jogo["league"]["id"] in LIGAS_MONITORADAS
        ]
        return jogos_filtrados
    
    print(f"[Cache API] Novo dia detectado. Consultando dados de hoje ({hoje_brt}) e de amanhã...")
    
    # Calcula o dia de amanhã BRT de forma segura
    amanha_brt = (agora_brt + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Busca partidas de hoje e de amanhã na API (Gasta apenas 2 requisições por dia)
    dados_hoje = fazer_requisicao_api(f"fixtures?date={hoje_brt}")
    dados_amanha = fazer_requisicao_api(f"fixtures?date={amanha_brt}")
    
    todos_jogos_crus = dados_hoje.get("response", []) + dados_amanha.get("response", [])
    
    # Filtro de Fuso Horário de Brasília (UTC-3)
    jogos_consolidados_hoje = []
    for jogo in todos_jogos_crus:
        data_utc_str = jogo["fixture"]["date"]
        # Trata formatos com Z ou offset nulo
        data_utc = datetime.fromisoformat(data_utc_str.replace("Z", "+00:00"))
        
        # Converte a hora de início do jogo para Brasília
        data_jogo_brt = data_utc - timedelta(hours=3)
        
        # Se a data de início em Brasília for exatamente hoje, o jogo pertence ao dia de hoje!
        if data_jogo_brt.strftime('%Y-%m-%d') == hoje_brt:
            jogos_consolidados_hoje.append(jogo)
            
    # Salva em cache os jogos consolidados para o dia de hoje
    if todos_jogos_crus:
        JOGOS_DO_DIA_RAW_CACHE = jogos_consolidados_hoje
        ULTIMA_CARGA_JOGOS = hoje_brt

    # Filtra pelas ligas monitoradas dinamicamente
    jogos_filtrados = [
        jogo for jogo in JOGOS_DO_DIA_RAW_CACHE 
        if jogo["league"]["id"] in LIGAS_MONITORADAS
    ]
    
    print(f"Balanço: Total jogos brutos do fuso de Brasília hoje: {len(JOGOS_DO_DIA_RAW_CACHE)} | Ativos filtrados: {len(jogos_filtrados)}")
    return jogos_filtrados

def forcar_atualizacao_cache() -> str:
    """
    Função de uso exclusivo do Dono. Força uma consulta real na API-Football,
    ignorando o cache existente, e reconstrói o banco de dados local bruto.
    """
    global JOGOS_DO_DIA_RAW_CACHE, ULTIMA_CARGA_JOGOS
    
    agora_brt = datetime.now(timezone.utc) - timedelta(hours=3)
    hoje_brt = agora_brt.strftime('%Y-%m-%d')
    amanha_brt = (agora_brt + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"[Forçar Cache] Consultando dados atualizados de hoje e amanhã na API-Football...")
    dados_hoje = fazer_requisicao_api(f"fixtures?date={hoje_brt}")
    dados_amanha = fazer_requisicao_api(f"fixtures?date={amanha_brt}")
    
    todos_jogos_crus = dados_hoje.get("response", []) + dados_amanha.get("response", [])
    
    is_erro = ("response" not in dados_hoje or dados_hoje.get("errors")) and ("response" not in dados_amanha or dados_amanha.get("errors"))
    if is_erro:
        return "❌ Falha ao forçar o cache na API de futebol. Verifique os limites e chaves."
        
    jogos_consolidados_hoje = []
    for jogo in todos_jogos_crus:
        data_utc_str = jogo["fixture"]["date"]
        data_utc = datetime.fromisoformat(data_utc_str.replace("Z", "+00:00"))
        data_jogo_brt = data_utc - timedelta(hours=3)
        if data_jogo_brt.strftime('%Y-%m-%d') == hoje_brt:
            jogos_consolidados_hoje.append(jogo)
            
    # Atualiza as variáveis de cache em memória
    JOGOS_DO_DIA_RAW_CACHE = jogos_consolidados_hoje
    ULTIMA_CARGA_JOGOS = hoje_brt
    
    jogos_filtrados = [
        jogo for jogo in JOGOS_DO_DIA_RAW_CACHE 
        if jogo["league"]["id"] in LIGAS_MONITORADAS
    ]
    
    return (
        f"✅ Cache de jogos de hoje reconstruído com sucesso!\n"
        f"• Total de partidas no mundo no fuso de Brasília hoje: {len(JOGOS_DO_DIA_RAW_CACHE)}\n"
        f"• Partidas ativas filtradas para o VAR: {len(jogos_filtrados)}"
    )

def obter_dados_recap_dia() -> List[Dict[str, Any]]:
    jogos = obter_jogos_do_dia()
    resumos_com_stats = []
    
    for jogo in jogos:
        status = jogo["fixture"]["status"]["short"]
        fixture_id = jogo["fixture"]["id"]
        
        if status in ["FT", "AET", "PEN"]:
            gols_casa = jogo["goals"]["home"]
            gols_fora = jogo["goals"]["away"]
            
            stats_jogo = {
                "campeonato": jogo["league"]["name"],
                "casa": jogo["teams"]["home"]["name"],
                "fora": jogo["teams"]["away"]["name"],
                "placar": f"{gols_casa} - {gols_fora}",
                "escanteios": "0 - 0",
                "cartoes_amarelos": "0 - 0",
                "cartoes_vermelhos": "0 - 0",
                "faltas": "0 - 0"
            }
            
            try:
                dados_stats = fazer_requisicao_api(f"fixtures/statistics?fixture={fixture_id}")
                stats_response = dados_stats.get("response", [])
                
                time.sleep(3)
                
                for team_stat in stats_response:
                    equipe = "home" if team_stat["team"]["name"] == jogo["teams"]["home"]["name"] else "away"
                    for s in team_stat["statistics"]:
                        tipo = s["type"]
                        valor = s["value"] if s["value"] is not None else 0
                        
                        if tipo == "Corner Kicks":
                            idx = 0 if equipe == "home" else 1
                            partes = stats_jogo["escanteios"].split(" - ")
                            partes[idx] = str(valor)
                            stats_jogo["escanteios"] = " - ".join(partes)
                        elif tipo == "Yellow Cards":
                            idx = 0 if equipe == "home" else 1
                            partes = stats_jogo["cartoes_amarelos"].split(" - ")
                            partes[idx] = str(valor)
                            stats_jogo["cartoes_amarelos"] = " - ".join(partes)
                        elif tipo == "Red Cards":
                            idx = 0 if equipe == "home" else 1
                            partes = stats_jogo["cartoes_vermelhos"].split(" - ")
                            partes[idx] = str(valor)
                            stats_jogo["cartoes_vermelhos"] = " - ".join(partes)
                        elif tipo == "Fouls":
                            idx = 0 if equipe == "home" else 1
                            partes = stats_jogo["faltas"].split(" - ")
                            partes[idx] = str(valor)
                            stats_jogo["faltas"] = " - ".join(partes)
            except Exception as e:
                print(f"Erro ao obter estatísticas detalhadas para partida {fixture_id}: {e}")
                
            resumos_com_stats.append(stats_jogo)
        else:
            resumos_com_stats.append({
                "campeonato": jogo["league"]["name"],
                "casa": jogo["teams"]["home"]["name"],
                "fora": jogo["teams"]["away"]["name"],
                "placar": "Nao iniciado ou Em andamento",
                "escanteios": "N/A", "cartoes_amarelos": "N/A", "cartoes_vermelhos": "N/A", "faltas": "N/A"
            })
            
    return resumos_com_stats

def gerar_resumo_diario_ia(dados_recap: List[Dict[str, Any]]) -> str:
    try:
        client = obter_cliente_gemini()
        
        prompt = (
            "Você é o analista-chefe da cabine do 'VAR do Lucro'. Escreva um balanço diário de fechamento de mercado "
            "altamente profissional, técnico e ultra-resumido para a nossa comunidade de investimentos esportivos.\n\n"
            
            "INSTRUÇÃO DE CONTEÚDO COMPACTO (MUITO IMPORTANTE):\n"
            "Você deve incluir todas as informações estatísticas e de auditoria de Greens/Reds de cada partida concluída, "
            "mas de forma extremamente sintetizada e curta para ocupar o menor espaço vertical possível no celular.\n"
            "Use rigorosamente esta estrutura enxuta de 3 linhas por partida para consolidar tudo:\n\n"
            "⚽ [Time Casa Traduzido] [Gols Casa] - [Gols Fora] [Time Fora Traduzido]\n"
            "📐 Cantos: [Casa]v[Fora] | 🟨 Cartões: [Casa]v[Fora] | ⚡ Faltas: [Casa]v[Fora]\n"
            "🟢 Over 2.5 Gols: [GREEN ou RED] | Ambas Marcam: [GREEN ou RED] | Over 9.5 Cantos: [GREEN ou RED] | Over 4.5 Cartões: [GREEN ou RED]\n"
            "──────────────────────\n\n"
            
            "INSTRUÇÕES DE AUDITORIA:\n"
            "Com base nos dados reais fornecidos abaixo, classifique cada um dos 4 mercados acima de forma exata:\n"
            "- Over 2.5 Gols -> GREEN 🟢 se a soma de gols for maior que 2.5 (caso contrário RED 🔴)\n"
            "- Ambas Marcam -> GREEN 🟢 se ambos os times marcaram gols (caso contrário RED 🔴)\n"
            "- Over 9.5 Cantos -> GREEN 🟢 se a soma de escanteios for maior ou igual a 10 (caso contrário RED 🔴)\n"
            "- Over 4.5 Cartões -> GREEN 🟢 se a soma de cartões amarelos for maior ou igual a 5 (caso contrário RED 🔴)\n\n"
            
            "INSTRUÇÕES DE FORMATAÇÃO E TRADUÇÃO:\n"
            "1. Agrupe as partidas por campeonato escrevendo o nome do campeonato acima de cada bloco de jogos.\n"
            "2. Traduza os nomes de todos os times, países e ligas para o Português do Brasil.\n"
            "3. Escreva um parágrafo curtíssimo de fechamento e motivação no final (máximo 2 linhas).\n"
            "4. NÃO use asteriscos (*) em nenhuma parte da mensagem.\n"
            "5. Use emojis moderados e quebras de linha elegantes para organizar as seções de forma que seja agradável.\n\n"
            f"Dados consolidados das partidas de hoje:\n{dados_recap}"
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Erro ao gerar resumo diário avançado via IA: {e}")
        return "Erro ao processar o fechamento de mercado detalhado."

def gerar_cronograma_diario_ia(jogos: List[Dict[str, Any]]) -> str:
    try:
        client = obter_cliente_gemini()
        
        lista_resumida = []
        for jogo in jogos:
            # Captura o estádio de forma totalmente segura e blindada contra "NoneType" da API
            venue_dict = jogo["fixture"].get("venue")
            venue_name = ""
            city_name = ""
            if isinstance(venue_dict, dict):
                venue_name = venue_dict.get("name") if venue_dict.get("name") else ""
                city_name = venue_dict.get("city") if venue_dict.get("city") else ""
                
            estadio_completo = f"Estádio de {venue_name}" if venue_name else ""
            if city_name and estadio_completo:
                estadio_completo += f" - {city_name}"

            lista_resumida.append({
                "campeonato": jogo["league"]["name"],
                "casa": jogo["teams"]["home"]["name"],
                "fora": jogo["teams"]["away"]["name"],
                "hora_utc": jogo["fixture"]["date"],
                "estadio": estadio_completo
            })

        prompt = (
            "Você é o 'VAR do Lucro'. Organize a lista de partidas de futebol abaixo em um cronograma diário super elegante.\n\n"
            "INSTRUÇÃO DE ESTILO E CARTÕES (MUITO IMPORTANTE):\n"
            "Você deve imitar o visual de cartões individuais para cada partida usando linhas divisórias horizontais exatas.\n"
            "Cada partida deve ser escrita exatamente neste formato estruturado de 4 linhas, sem tabelas horizontais ou desalinhamentos:\n\n"
            "──────────────────────\n"
            "🗓️ [DIA] [MÊS EM MAIÚSCULO (ex: JUN)], [HORA CONVERTIDA PARA O HORÁRIO DE BRASÍLIA UTC-3]\n"
            "⚽ [Nome do Time Casa Traduzido] - [Nome do Time Fora Traduzido]\n"
            "🏟️ [Estádio e Cidade Traduzidos (se fornecido, ex: Estádio de Boston / Filadélfia. Se não houver, ignore esta linha)]\n"
            "──────────────────────\n\n"
            "REGRAS DE CONVERSÃO E TRADUÇÃO:\n"
            "1. Agrupe as partidas por Campeonato/Liga escrevendo o título do campeonato acima do bloco de jogos.\n"
            "2. Traduza os nomes de times, países e ligas para o Português do Brasil.\n"
            "3. NÃO use asteriscos (*) em hipótese alguma na resposta final.\n"
            "4. Adicione emojis esportivos ou as bandeirinhas dos países (ex: 🇧🇷, 🏴󠁧󠁢󠁳󠁣󠁴󠁿) se forem seleções.\n\n"
            f"Lista de jogos do dia:\n{lista_resumida}"
        )
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        print(f"Erro ao gerar cronograma de jogos via IA: {e}")
        return "Erro ao construir o cronograma diário de partidas."

def gerar_relatorio_pre_jogo(fixture: Dict[str, Any]) -> str:
    try:
        client = obter_cliente_gemini()
        liga = fixture["league"]["name"]
        time_casa = fixture["teams"]["home"]["name"]
        time_fora = fixture["teams"]["away"]["name"]
        
        prompt = (
            f"Você é a IA analista-chefe da cabine do 'VAR do Lucro', especialista em Engenharia de Prompt e Modelagem Estatística Avançada para apostas esportivas de valor (+EV).\n"
            f"Sua missão é realizar uma análise estatística pré-jogo em tempo real (exatamente 1 hora antes do início, considerando desfalques e escalações confirmadas de última hora de hoje) para o confronto: {time_casa} vs {time_fora} pela liga '{liga}'.\n\n"
            
            "REGRAS DE ANÁLISE MATEMÁTICA (Use a pesquisa do Google em tempo real para obter dados de odds atuais, xG recente das equipes, árbitro escalado e desfalques):\n"
            "1. MODELAGEM DE GOLS: Cruze as projeções de xG gerado e concedido recente dos dois times. Identifique tendências ou anomalias estruturais.\n"
            "2. CÁLCULO DE PROBABILIDADE E +EV: Converta as odds médias reais atuais das casas para probabilidade implícita (Probabilidade = 1 / odd). Calcule a sua própria probabilidade real baseada na força dos elencos, desfalques de última hora e histórico. Se a sua probabilidade for maior que a da casa, você encontrou Valor Esperado Positivo (+EV). Indique este mercado.\n"
            "3. LINHAS SECUNDÁRIAS: Cruze o comportamento agressivo (média de faltas dos times) com o rigor histórico do árbitro escalado para projetar os cartões. Cruze o volume de APM (Ataques Perigosos por Minuto) com a média recente de escanteios das equipes.\n\n"
            
            "REGRAS RÍGIDAS DE FORMATAÇÃO E TRADUÇÃO:\n"
            "- NÃO use asteriscos (*) em nenhuma parte da resposta final (substitua por traços ou outros emojis para manter o visual limpo).\n"
            "- Traduza obrigatoriamente todos os nomes de times, países e ligas para o Português do Brasil no relatório final.\n"
            "- Seja estritamente direto, objetivo e resumido, entregando as informações exatamente seguindo este modelo de resposta de alta fidelidade visual:\n\n"
            
            "🔍 RELATÓRIO MATEMÁTICO - VAR DO LUCRO\n"
            f"⚽ [Nome do Time Casa Traduzido] vs [Nome do Time Fora Traduzido]\n"
            f"🏆 [Nome da Liga Traduzido] (28/06/2026)\n\n"
            
            "- Resultado (1X2 ou Handicap): [Indicação do mercado exato de resultado / handicap] (Probabilidade calculada pelo VAR: [X]% | Odd da casa: [X] | Implicada: [X]%)\n\n"
            "- Gols (Over/Under e BTTS): [Linha sugerida baseada em xG] (Projeção de xG combinado: [X] gols | Probabilidade VAR: [X]% | Odd da casa: [X])\n\n"
            "- Escanteios: [Linha sugerida de cantos] (Média projetada combinada: [X] cantos | Justificativa ultra-curta)\n\n"
            "- Cartões / Faltas: [Linha sugerida de cartões] (Média de faltas: [X] | Árbitro escalado: [Nome do árbitro] com média de [X] cartões/jogo | Justificativa ultra-curta)\n\n"
            "- Aposta de Maior Valor (+EV): [Mercado específico desajustado pelas casas]\n"
            "  • Odd da casa: [X] (Probabilidade implícita: [X]%)\n"
            "  • Probabilidade real calculada pelo VAR: [X]%\n"
            "  • Valor Esperado (+EV): [X]%\n"
            "  • Critério de Kelly Recomendado: [X]% da banca (Sugerir stake fracionária segura de 1% a 3% para proteção da banca)\n\n"
            "👉 Aposta sugerida? Confira na sua Casa favorita! Jogue com responsabilidade 🔞"
        )

        configuracao = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=configuracao)
        return response.text
    except Exception as e:
        print(f"Erro ao processar relatório pré-jogo matemático avançado: {e}")
        return f"Não foi possível processar o Relatório de Inteligência para {time_casa} vs {time_fora} no momento."

# =====================================================================
# SEÇÃO 2: ANÁLISE EM TEMPO REAL (SOLICITAÇÃO DE JOGO AO VIVO)
# =====================================================================

def buscar_jogo_ao_vivo_por_time(nome_orig: str, nome_trad: str) -> Optional[Dict[str, Any]]:
    """
    Busca no catálogo de jogos ao vivo ativos. Compara tanto o nome original (em português)
    quanto o nome traduzido (em inglês) para garantir compatibilidade total de clubes e seleções.
    """
    dados_live = fazer_requisicao_api("fixtures?live=all")
    jogos_ao_vivo = dados_live.get("response", [])
    
    orig_min = nome_orig.lower().strip()
    trad_min = nome_trad.lower().strip()
    
    for jogo in jogos_ao_vivo:
        casa = jogo["teams"]["home"]["name"].lower()
        fora = jogo["teams"]["away"]["name"].lower()
        
        # Verificação direta de segurança (sem helpers para evitar NameError)
        if orig_min in casa or orig_min in fora or trad_min in casa or trad_min in fora:
            fixture_id = jogo["fixture"]["id"]
            dados_stats = fazer_requisicao_api(f"fixtures/statistics?fixture={fixture_id}")
            stats = dados_stats.get("response", [])
            return {"fixture": jogo, "statistics": stats}
    return None

def gerar_barra_comparativa(val_casa: float, val_fora: float) -> str:
    total = val_casa + val_fora
    if total == 0:
        return "⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪"
    pontos_casa = round((val_casa / total) * 10)
    pontos_fora = 10 - pontos_casa
    return "🔵" * pontos_casa + "🔴" * pontos_fora

def analisar_ao_vivo_e_formatar(dados_api: Dict[str, Any]) -> str:
    fixture = dados_api["fixture"]
    liga = fixture["league"]["name"]
    time_casa = fixture["teams"]["home"]["name"]
    time_fora = fixture["teams"]["away"]["name"]
    tempo_minutos = fixture["fixture"]["status"]["elapsed"]
    gols_casa = fixture["goals"]["home"]
    gols_fora = fixture["goals"]["away"]
    estatisticas_brutas = dados_api["statistics"]

    stats_parsed = {
        "home": {"attacks": 0, "corners": 0, "shots": 0, "on_target": 0, "possession": 50},
        "away": {"attacks": 0, "corners": 0, "shots": 0, "on_target": 0, "possession": 50}
    }

    for item in estatisticas_brutas:
        equipe = "home" if item["team"]["name"] == time_casa else "away"
        for stat in item["statistics"]:
            tipo = stat["type"]
            valor = stat["value"]
            if valor is None: valor = 0
            if isinstance(valor, str) and "%" in valor:
                valor = int(valor.replace("%", ""))
                
            if tipo == "Dangerous Attacks": stats_parsed[equipe]["attacks"] = int(valor)
            elif tipo == "Corner Kicks": stats_parsed[equipe]["corners"] = int(valor)
            elif tipo == "Total Shots": stats_parsed[equipe]["shots"] = int(valor)
            elif tipo == "Shots on Goal": stats_parsed[equipe]["on_target"] = int(valor)
            elif tipo == "Ball Possession": stats_parsed[equipe]["possession"] = int(valor)

    barra_ataques = gerar_barra_comparativa(stats_parsed["home"]["attacks"], stats_parsed["away"]["attacks"])
    barra_cantos = gerar_barra_comparativa(stats_parsed["home"]["corners"], stats_parsed["away"]["corners"])
    barra_chutes = gerar_barra_comparativa(stats_parsed["home"]["shots"], stats_parsed["away"]["shots"])
    barra_alvo = gerar_barra_comparativa(stats_parsed["home"]["on_target"], stats_parsed["away"]["on_target"])
    barra_posse = gerar_barra_comparativa(stats_parsed["home"]["possession"], stats_parsed["away"]["possession"])

    try:
        client = obter_cliente_gemini()
        prompt_ia = (
            f"Analise o ritmo deste jogo aos {tempo_minutos} minutos de jogo. Placar atual: {gols_casa} - {gols_fora}.\\n"
            f"Ataques Perigosos: {stats_parsed['home']['attacks']} vs {stats_parsed['away']['attacks']}.\\n"
            f"Chutes no gol: {stats_parsed['home']['on_target']} vs {stats_parsed['away']['on_target']}.\\n\\n"
            "Escolha apenas uma das opções abaixo para o sinal e não escreva nenhuma outra palavra:\\n"
            "- 'Mais 0.5 Gols na partida'\\n"
            "- 'Mais 1 Gol na partida'\\n"
            "- 'Sem entrada recomendada'"
        )
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_ia)
        sinal = response.text.strip().replace("'", "").replace('"', "")
    except Exception as e:
        print(f"Erro na IA ao decidir sinal: {e}")
        sinal = "Mais 0.5 Gols na partida"

    casas_sugestoes = [
        ("Superbet", "https://superbet.com"),
        ("Bet365", "https://www.bet365.com"),
        ("EstrelaBet", "https://estrelabet.com"),
        ("Novibet", "https://novibet.com"),
        ("Sportingbet", "https://sportingbet.com")
    ]
    casa_sugerida_1, link_1 = random.choice(casas_sugestoes)
    
    # Formatação visual enxuta em blocos verticais compactos
    mensagem_final = (
        "💎 [Sinal Confirmado - VAR do Lucro PREMIUM]\\n\\n"
        f"🏟 {liga}\\n"
        f"⚽ {time_casa} v {time_fora}\n"
        f"🕐 {tempo_minutos} minutos\n"
        f"🔢 Placar do jogo: {gols_casa} - {gols_fora}\n\n"
        "📊 Dados do jogo (Mandante - Visitante):\\n\\n"
        f"⚡ Investidas ofensivas: {stats_parsed['home']['attacks']} - {stats_parsed['away']['attacks']}\\n"
        f"[ {barra_ataques} ]\\n\\n"
        f"📐 Escanteios: {stats_parsed['home']['corners']} - {stats_parsed['away']['corners']}\\n"
        f"[ {barra_cantos} ]\\n\\n"
        f"👟 Arremates: {stats_parsed['home']['shots']} - {stats_parsed['away']['shots']}\\n"
        f"[ {barra_chutes} ]\\n\\n"
        f"🎯 Tentativas no alvo: {stats_parsed['home']['on_target']} - {stats_parsed['away']['on_target']}\\n"
        f"[ {barra_alvo} ]\\n\\n"
        f"📈 Controle da bola: {stats_parsed['home']['possession']}% - {stats_parsed['away']['possession']}%\\n"
        f"[ {barra_posse} ]\\n\\n"
        f"🔥 Sinal: {sinal}\\n\\n"
        "↪ Confira nas casas:\\n"
        f"🎲 Pegue na [{casa_sugerida_1}]({link_1})\\n\\n"
        "Jogue com responsabilidade 🔞"
    )

    return mensagem_final

# =====================================================================
# SEÇÃO 3: CONTROLE DE LIGAS, AGENDAMENTOS E CRONOGRAMAS
# =====================================================================

def adicionar_liga_monitorada(league_id: int) -> bool:
    global LIGAS_MONITORADAS
    if league_id not in LIGAS_MONITORADAS:
        LIGAS_MONITORADAS.append(league_id)
        return True
    return False

def remover_liga_monitorada(league_id: int) -> bool:
    global LIGAS_MONITORADAS
    if league_id in LIGAS_MONITORADAS:
        LIGAS_MONITORADAS.remove(league_id)
        return True
    return False

def listar_ligas_monitoradas() -> List[int]:
    return LIGAS_MONITORADAS

def buscar_ids_ligas(termo_busca: str) -> List[Dict[str, Any]]:
    dados_leagues = fazer_requisicao_api(f"leagues?search={termo_busca}")
    dados = dados_leagues.get("response", [])
    return [{"id": item["league"]["id"], "nome": item["league"]["name"], "pais": item["country"]["name"]} for item in dados]

def obter_estatisticas_time(team_id: int, league_id: int, season: int) -> Optional[Dict[str, Any]]:
    dados = fazer_requisicao_api(f"teams/statistics?team={team_id}&league={league_id}&season={season}")
    return dados.get("response")

def obter_elenco_time(team_id: int) -> List[Dict[str, Any]]:
    dados_squad = fazer_requisicao_api(f"players/squads?team={team_id}")
    dados = dados_squad.get("response", [])
    if dados:
        return dados[0].get("players", [])
    return []

def buscar_time_por_nome(nome_time: str) -> Optional[Dict[str, Any]]:
    dados_teams = fazer_requisicao_api(f"teams?search={nome_time}")
    dados = dados_teams.get("response", [])
    if dados:
        return dados[0]
    return None

def verificar_e_enviar_cronograma(bot) -> bool:
    global ULTIMO_DIA_CRONOGRAMA
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    topico_pre_jogo = os.getenv("TOPICO_PRE_JOGO")
    if not chat_id or not topico_pre_jogo:
        return False
    agora_brt = datetime.now(timezone.utc) - timedelta(hours=3)
    dia_atual_brt = agora_brt.strftime('%Y-%m-%d')
    if dia_atual_brt != ULTIMO_DIA_CRONOGRAMA:
        print(f"Novo dia detectado ({dia_atual_brt} BRT). Enviando cronograma...")
        jogos = obter_jogos_do_dia()
        if jogos:
            texto_cronograma = gerar_cronograma_diario_ia(jogos)
            try:
                bot.send_message(chat_id=chat_id, text=texto_cronograma, message_thread_id=int(topico_pre_jogo))
                ULTIMO_DIA_CRONOGRAMA = dia_atual_brt
                return True
            except Exception as e:
                print(f"Erro ao disparar: {e}")
        else:
            ULTIMO_DIA_CRONOGRAMA = dia_atual_brt
    return False

def verificar_e_enviar_pre_jogos(bot) -> int:
    """
    Varre os jogos do dia e gerencia os disparos do relatório pré-jogo de 1 hora
    e os alertas de contagem regressiva por IA de 3h, 2h e 10m (Sem gasto de API).
    """
    global JOGOS_ANALISADOS, ALERTAS_ENVIADOS
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    topico_pre_jogo = os.getenv("TOPICO_PRE_JOGO")
    if not chat_id or not topico_pre_jogo:
        return 0
        
    jogos = obter_jogos_do_dia()
    agora = datetime.now(timezone.utc)
    enviados = 0
    
    for jogo in jogos:
        fixture_id = jogo["fixture"]["id"]
        time_casa = jogo["teams"]["home"]["name"]
        time_fora = jogo["teams"]["away"]["name"]
        
        # Traduz os nomes para os alertas rápidos ficarem bonitos em português
        try:
            from deep_translator import GoogleTranslator
            time_casa_pt = GoogleTranslator(source='en', target='pt').translate(time_casa)
            time_fora_pt = GoogleTranslator(source='en', target='pt').translate(time_fora)
        except Exception:
            time_casa_pt, time_fora_pt = time_casa, time_fora

        data_jogo_str = jogo["fixture"]["date"]
        data_jogo = datetime.fromisoformat(data_jogo_str.replace("Z", "+00:00"))
        diferenca_tempo = data_jogo - agora
        minutos_para_comecar = diferenca_tempo.total_seconds() / 60
        
        # 1. ALERTA DE 3 HORAS ANTES
        if 170 <= minutos_para_comecar <= 190:
            chave_alerta = f"{fixture_id}_3h"
            if chave_alerta not in ALERTAS_ENVIADOS:
                prompt = (
                    f"Escreva um alerta curto, divertido e enérgico informando que a partida entre {time_casa_pt} e {time_fora_pt} começará em exatamente 3 horas.\\n"
                    "Tema do grupo: 'VAR do Lucro'. Faça piadas sobre os analistas estarem preparando a tela ou ajustando os óculos para a análise.\\n"
                    "REGRA RÍGIDA: NÃO use asteriscos (*) no texto final. Máximo de 2 linhas."
                )
                alerta_texto = gerar_texto_ia_local(prompt)
                try:
                    bot.send_message(chat_id=chat_id, text=alerta_texto, message_thread_id=int(topico_pre_jogo))
                    ALERTAS_ENVIADOS.add(chave_alerta)
                    enviados += 1
                except Exception as e:
                    print(f"Erro alerta 3h: {e}")
                    
        # 2. ALERTA DE 2 HORAS ANTES
        elif 110 <= minutos_para_comecar <= 130:
            chave_alerta = f"{fixture_id}_2h"
            if chave_alerta not in ALERTAS_ENVIADOS:
                prompt = (
                    f"Escreva um alerta curto, divertido e enérgico informando que a partida entre {time_casa_pt} e {time_fora_pt} começará em exatamente 2 horas.\\n"
                    "Tema do grupo: 'VAR do Lucro'. Diga de forma engraçada para a galera ir se preparando para as análises que estão chegando.\\n"
                    "REGRA RÍGIDA: NÃO use asteriscos (*) no texto final. Máximo de 2 linhas."
                )
                alerta_texto = gerar_texto_ia_local(prompt)
                try:
                    bot.send_message(chat_id=chat_id, text=alerta_texto, message_thread_id=int(topico_pre_jogo))
                    ALERTAS_ENVIADOS.add(chave_alerta)
                    enviados += 1
                except Exception as e:
                    print(f"Erro alerta 2h: {e}")

        # 3. ALERTA DE 1 HORA ANTES (ENVIO DO RELATÓRIO DO JOGO)
        elif 50 <= minutos_para_comecar <= 70:
            if fixture_id not in JOGOS_ANALISADOS:
                try:
                    relatorio = gerar_relatorio_pre_jogo(jogo)
                    bot.send_message(chat_id=chat_id, text=relatorio, message_thread_id=int(topico_pre_jogo))
                    JOGOS_ANALISADOS.add(fixture_id)
                    enviados += 1
                    time.sleep(2)
                except Exception as e:
                    print(f"Falha ao enviar relatório pré-jogo: {e}")

        # 4. ALERTA DE 10 MINUTOS ANTES
        elif 5 <= minutos_para_comecar <= 15:
            chave_alerta = f"{fixture_id}_10m"
            if chave_alerta not in ALERTAS_ENVIADOS:
                prompt = (
                    f"Escreva um alerta curto, urgente e divertido avisando que a partida entre {time_casa_pt} e {time_fora_pt} começará em apenas 10 minutos!\\n"
                    "Tema do grupo: 'VAR do Lucro'. Avise os membros a prepararem os dedos na tela e reverem suas stakes, pois a bola já vai rolar.\\n"
                    "REGRA RÍGIDA: NÃO use asteriscos (*) no texto final. Máximo de 2 linhas."
                )
                alerta_texto = gerar_texto_ia_local(prompt)
                try:
                    bot.send_message(chat_id=chat_id, text=alerta_texto, message_thread_id=int(topico_pre_jogo))
                    ALERTAS_ENVIADOS.add(chave_alerta)
                    enviados += 1
                except Exception as e:
                    print(f"Erro alerta 10m: {e}")
                    
    return enviados