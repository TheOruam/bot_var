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

API_FOOTBALL_URL = "https://v3.football.api-sports.io"

def obter_cliente_gemini() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chave de ambiente 'GEMINI_API_KEY' não configurada.")
    return genai.Client(api_key=api_key)

# =====================================================================
# SISTEMA DE REDUNDÂNCIA DE APIS (FALLBACK MULTI-CHAVE BLINDADO)
# =====================================================================

def fazer_requisicao_api(endpoint: str) -> Dict[str, Any]:
    raw_keys = os.getenv("API_FOOTBALL_KEY", "")
    chaves = [k.strip() for k in raw_keys.split(",") if k.strip()]
    
    if not chaves:
        print("❌ [Fallback API] Erro: Nenhuma API_FOOTBALL_KEY foi configurada no Render.")
        return {"response": [], "errors": "Chave não configurada"}

    ultimo_erro = None
    headers = {'x-rapidapi-host': 'v3.football.api-sports.io'}

    for i, chave in enumerate(chaves):
        headers['x-rapidapi-key'] = chave
        try:
            url = f"{API_FOOTBALL_URL}/{endpoint}"
            resposta = requests.get(url, headers=headers, timeout=12)
            dados = resposta.json()
            
            is_erro = "response" not in dados or dados.get("errors")
            
            if is_erro:
                erro_detalhado = dados.get("errors") if dados.get("errors") else dados
                print(f"⚠️ [Fallback API] Chave {i+1} falhou. Motivo: {erro_detalhado}. Tentando chave reserva...")
                ultimo_erro = erro_detalhado
                continue
                
            return dados
            
        except Exception as e:
            print(f"⚠️ [Fallback API] Erro de rede com a chave {i+1}: {e}. Pulando para a próxima...")
            ultimo_erro = str(e)
            
    print("❌ [Fallback API] Alerta Crítico: Todas as chaves de API fornecidas falharam.")
    return {"response": [], "errors": ultimo_erro}

# =====================================================================
# SEÇÃO 1: ANÁLISE PRÉ-JOGO, CRONOGRAMA E RESUMO DETALHADO COM VERIFICAÇÃO DE GREENS
# =====================================================================

def obter_jogos_do_dia() -> List[Dict[str, Any]]:
    agora_brt = datetime.now(timezone.utc) - timedelta(hours=3)
    hoje_brt = agora_brt.strftime('%Y-%m-%d')
    
    dados = fazer_requisicao_api(f"fixtures?date={hoje_brt}")
    todos_jogos = dados.get("response", [])
    
    jogos_filtrados = [
        jogo for jogo in todos_jogos 
        if jogo["league"]["id"] in LIGAS_MONITORADAS
    ]
    
    print(f"Data BRT consultada: {hoje_brt} | Total jogos mundo: {len(todos_jogos)} | Filtrados: {len(jogos_filtrados)}")
    return jogos_filtrados

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
                "escanteios": "N/A",
                "cartoes_amarelos": "N/A",
                "cartoes_vermelhos": "N/A",
                "faltas": "N/A"
            })
            
    return resumos_com_stats

def gerar_resumo_diario_ia(dados_recap: List[Dict[str, Any]]) -> str:
    try:
        client = obter_cliente_gemini()
        
        prompt = (
            "Você é o analista-chefe da cabine do 'VAR do Lucro'. Escreva um balanço diário de fechamento de mercado "
            "altamente profissional, detalhado e técnico para a nossa comunidade de investimentos esportivos.\n\n"
            "INSTRUÇÕES DE AUDITORIA E VERIFICAÇÃO (MUITO IMPORTANTE):\n"
            "Com base nos resultados e dados das partidas fornecidos abaixo, monte para cada jogo finalizado um painel de "
            "verificação mostrando quais dos mercados padrão seriam classificados como GREEN 🟢 ou RED 🔴.\n"
            "Exemplos de auditoria que você deve fazer:\n"
            "- Se a soma de gols da partida for maior que 2.5: Over 2.5 Gols -> GREEN 🟢 (caso contrário: RED 🔴)\n"
            "- Se ambos os times marcaram gols (placar ex: 2-1, 1-1): Ambas Marcam Sim -> GREEN 🟢 (caso contrário: RED 🔴)\n"
            "- Se a soma dos escanteios for maior ou igual a 10: Over 9.5 Escanteios -> GREEN 🟢 (caso contrário: RED 🔴)\n"
            "- Se a soma de cartões amarelos for maior ou igual a 5: Over 4.5 Cartões -> GREEN 🟢 (caso contrário: RED 🔴)\n\n"
            "INSTRUÇÕES DE FORMATAÇÃO:\n"
            "1. Agrupe as partidas por campeonato, listando o placar e as estatísticas de cada time (Gols, Escanteios, Cartões, Faltas).\n"
            "2. Traduza obrigatoriamente os nomes de todos os times, países e ligas para o Português do Brasil.\n"
            "3. Escreva uma análise curta no final destacando como foi o rendimento estatístico do dia de hoje de forma geral.\n"
            "4. NÃO use asteriscos (*) em nenhuma parte da mensagem.\n"
            "5. Use emojis moderados e quebras de linha elegantes para organizar as seções de forma que seja agradável de ler no celular.\n\n"
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
            venue = jogo["fixture"]["venue"]["name"] if jogo["fixture"]["venue"]["name"] else ""
            city = jogo["fixture"]["venue"]["city"] if jogo["fixture"]["venue"]["city"] else ""
            estadio_completo = f"Estádio de {venue}" if venue else ""
            if city and estadio_completo:
                estadio_completo += f" - {city}"

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
            "2. Traduza os nomes de times, países e ligas para o Português do Brasil (ex: 'Brazil' vira 'Brasil', 'Scotland' vira 'Escócia').\n"
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
            f"Você é o 'VAR do Lucro', uma IA especialista em apostas esportivas de valor (+EV).\n"
            f"Faça uma análise ULTRA-RESUMIDA e DIRETA do confronto: {time_casa} vs {time_fora} pela liga '{liga}'.\n\n"
            f"REGRAS:\n"
            f"- Indique os 2 mercados de maior valor entre Gols, Resultado, Escanteios ou Cartões.\n"
            f"- Justificativas curtas de até 1 linha por palpite.\n"
            f"- Traduza obrigatoriamente todos os nomes dos times para o Português do Brasil no relatório final.\n"
            f"- NÃO use asteriscos (*) em hipótese alguma na resposta."
        )

        configuracao = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=configuracao
        )
        return response.text
    except Exception as e:
        print(f"Erro ao processar relatório pré-jogo: {e}")
        return f"Não foi possível processar o Relatório de Inteligência para {time_casa} vs {time_fora} no momento."

# =====================================================================
# SEÇÃO 2: ANÁLISE EM TEMPO REAL (SOLICITAÇÃO DE JOGO AO VIVO)
# =====================================================================

def buscar_jogo_ao_vivo_por_time(nome_time: str) -> Optional[Dict[str, Any]]:
    dados_live = fazer_requisicao_api("fixtures?live=all")
    jogos_ao_vivo = dados_live.get("response", [])
    
    nome_time_min = nome_time.lower().strip()
    
    for jogo in jogos_ao_vivo:
        casa = jogo["teams"]["home"]["name"].lower()
        fora = jogo["teams"]["away"]["name"].lower()
        
        if nome_time_min in casa or nome_time_min in fora:
            fixture_id = jogo["fixture"]["id"]
            
            dados_stats = fazer_requisicao_api(f"fixtures/statistics?fixture={fixture_id}")
            stats = dados_stats.get("response", [])
            
            return {
                "fixture": jogo,
                "statistics": stats
            }
    return None

def gerar_barra_comparativa(val_casa: float, val_fora: float) -> str:
    """Gera uma barra comparativa com bolinhas azuis e vermelhas."""
    total = val_casa + val_fora
    if total == 0:
        return "⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪"
    pontos_casa = round((val_casa / total) * 10)
    pontos_fora = 10 - pontos_casa
    return "🔵" * pontos_casa + "🔴" * pontos_fora

def analisar_ao_vivo_e_formatar(dados_api: Dict[str, Any]) -> str:
    """Gera o sinal Over Gols no modelo enxuto e impecável do VAR do Lucro."""
    fixture = dados_api["fixture"]
    liga = fixture["league"]["name"]
    time_casa = fixture["teams"]["home"]["name"]
    time_fora = fixture["teams"]["away"]["name"]
    tempo_minutos = fixture["fixture"]["status"]["elapsed"]
    gols_casa = fixture["goals"]["home"]
    gols_fora = fixture["goals"]["away"]
    estatisticas_brutas = dados_api["statistics"]

    # Dicionário auxiliar para capturar as estatísticas
    stats_parsed = {
        "home": {"attacks": 0, "corners": 0, "shots": 0, "on_target": 0, "possession": 50},
        "away": {"attacks": 0, "corners": 0, "shots": 0, "on_target": 0, "possession": 50}
    }

    for item in estatisticas_brutas:
        equipe = "home" if item["team"]["name"] == time_casa else "away"
        for stat in item["statistics"]:
            tipo = stat["type"]
            valor = stat["value"]
            if valor is None:
                valor = 0
            if isinstance(valor, str) and "%" in valor:
                valor = int(valor.replace("%", ""))
                
            if tipo == "Dangerous Attacks":
                stats_parsed[equipe]["attacks"] = int(valor)
            elif tipo == "Corner Kicks":
                stats_parsed[equipe]["corners"] = int(valor)
            elif tipo == "Total Shots":
                stats_parsed[equipe]["shots"] = int(valor)
            elif tipo == "Shots on Goal":
                stats_parsed[equipe]["on_target"] = int(valor)
            elif tipo == "Ball Possession":
                stats_parsed[equipe]["possession"] = int(valor)

    # Gera as barras comparativas
    barra_ataques = gerar_barra_comparativa(stats_parsed["home"]["attacks"], stats_parsed["away"]["attacks"])
    barra_cantos = gerar_barra_comparativa(stats_parsed["home"]["corners"], stats_parsed["away"]["corners"])
    barra_chutes = gerar_barra_comparativa(stats_parsed["home"]["shots"], stats_parsed["away"]["shots"])
    barra_alvo = gerar_barra_comparativa(stats_parsed["home"]["on_target"], stats_parsed["away"]["on_target"])
    barra_posse = gerar_barra_comparativa(stats_parsed["home"]["possession"], stats_parsed["away"]["possession"])

    try:
        # A IA só decide a frase curta do sinal para evitar poluir a mensagem
        client = obter_cliente_gemini()
        prompt_ia = (
            f"Analise o ritmo deste jogo aos {tempo_minutos} minutos de jogo. Placar atual: {gols_casa} - {gols_fora}.\n"
            f"Ataques Perigosos: {stats_parsed['home']['attacks']} vs {stats_parsed['away']['attacks']}.\n"
            f"Chutes no gol: {stats_parsed['home']['on_target']} vs {stats_parsed['away']['on_target']}.\n\n"
            "Escolha apenas uma das opções abaixo para o sinal e não escreva nenhuma outra palavra:\n"
            "- 'Mais 0.5 Gols na partida'\n"
            "- 'Mais 1 Gol na partida'\n"
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
    
    # Formatação 100% rígida feita em Python (Livre de falhas da IA)
    mensagem_final = (
        "💎 [Sinal Confirmado - VAR do Lucro PREMIUM]\n\n"
        f"🏟 {liga}\n"
        f"⚽ {time_casa} v {time_fora}\n"
        f"🕐 {tempo_minutos} minutos\n"
        f"🔢 Placar do jogo: {gols_casa} - {gols_fora}\n\n"
        
        "📊 Dados do jogo (Mandante - Visitante):\n\n"
        
        f"⚡ Investidas ofensivas: {stats_parsed['home']['attacks']} - {stats_parsed['away']['attacks']}\n"
        f"[ {barra_ataques} ]\n\n"
        
        f"📐 Escanteios: {stats_parsed['home']['corners']} - {stats_parsed['away']['corners']}\n"
        f"[ {barra_cantos} ]\n\n"
        
        f"👟 Arremates: {stats_parsed['home']['shots']} - {stats_parsed['away']['shots']}\n"
        f"[ {barra_chutes} ]\n\n"
        
        f"🎯 Tentativas no alvo: {stats_parsed['home']['on_target']} - {stats_parsed['away']['on_target']}\n"
        f"[ {barra_alvo} ]\n\n"
        
        f"📈 Controle da bola: {stats_parsed['home']['possession']}% - {stats_parsed['away']['possession']}%\n"
        f"[ {barra_posse} ]\n\n"
        
        f"🔥 Sinal: {sinal}\n\n"
        
        "↪ Confira nas casas:\n"
        f"🎲 Pegue na [{casa_sugerida_1}]({link_1})\n\n"
        "Jogue com responsabilidade 🔞"
    )

    return mensagem_final

# =====================================================================
# SEÇÃO 3: CONTROLE DE LIGAS, AGENDAMENTOS E CRONOGRAMAS
# =====================================================================

LIGAS_MONITORADAS = [71, 72, 73, 1, 39, 140, 2]
JOGOS_ANALISADOS = set()
ULTIMO_DIA_CRONOGRAMA = ""

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
    global JOGOS_ANALISADOS
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    topico_pre_jogo = os.getenv("TOPICO_PRE_JOGO")
    if not chat_id or not topico_pre_jogo:
        return 0
    jogos = obter_jogos_do_dia()
    agora = datetime.now(timezone.utc)
    enviados = 0
    for jogo in jogos:
        fixture_id = jogo["fixture"]["id"]
        if fixture_id in JOGOS_ANALISADOS:
            continue
        data_jogo_str = jogo["fixture"]["date"]
        data_jogo = datetime.fromisoformat(data_jogo_str.replace("Z", "+00:00"))
        diferenca_tempo = data_jogo - agora
        minutos_para_comecar = diferenca_tempo.total_seconds() / 60
        if 50 <= minutos_para_comecar <= 70:
            try:
                relatorio = gerar_relatorio_pre_jogo(jogo)
                bot.send_message(chat_id=chat_id, text=relatorio, message_thread_id=int(topico_pre_jogo))
                JOGOS_ANALISADOS.add(fixture_id)
                enviados += 1
                time.sleep(2)
            except Exception as e:
                print(f"Falha ao enviar: {e}")
    return enviados