# analisador.py
import os
import time
import requests
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types
from google.genai.errors import APIError
from typing import Optional, Dict, Any, List

# Configurações de API externas
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
API_FOOTBALL_URL = "https://v3.football.api-sports.io"

def obter_cliente_gemini() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Chave de ambiente 'GEMINI_API_KEY' não configurada.")
    return genai.Client(api_key=api_key)

# =====================================================================
# SEÇÃO 1: ANÁLISE PRÉ-JOGO E CRONOGRAMA DIÁRIO (00:00 BRT)
# =====================================================================

def obter_jogos_do_dia() -> List[Dict[str, Any]]:
    if not API_FOOTBALL_KEY:
        print("Erro: API_FOOTBALL_KEY não foi configurada.")
        return []
    
    headers = {
        'x-rapidapi-host': 'v3.football.api-sports.io',
        'x-rapidapi-key': API_FOOTBALL_KEY
    }
    
    # Obtém o dia atual no Horário de Brasília (UTC-3)
    agora_brt = datetime.now(timezone.utc) - timedelta(hours=3)
    hoje_brt = agora_brt.strftime('%Y-%m-%d')
    
    try:
        # Busca todas as partidas do dia atual na API
        resposta = requests.get(f"{API_FOOTBALL_URL}/fixtures?date={hoje_brt}", headers=headers, timeout=15)
        todos_jogos = resposta.json().get("response", [])
        
        # Filtra localmente apenas pelas ligas monitoradas
        jogos_filtrados = [
            jogo for jogo in todos_jogos 
            if jogo["league"]["id"] in LIGAS_MONITORADAS
        ]
        
        print(f"Data BRT consultada: {hoje_brt} | Total jogos mundo: {len(todos_jogos)} | Filtrados: {len(jogos_filtrados)}")
        return jogos_filtrados
        
    except Exception as e:
        print(f"Erro ao buscar partidas agendadas para o dia de hoje: {e}")
        return []

def gerar_cronograma_diario_ia(jogos: List[Dict[str, Any]]) -> str:
    """
    Envia a lista bruta de partidas do dia para o Gemini formatar um cronograma
    limpo, traduzido e convertido para o Horário de Brasília (UTC-3).
    """
    try:
        client = obter_cliente_gemini()
        
        # Simplifica os dados para poupar tokens de processamento
        lista_resumida = []
        for jogo in jogos:
            lista_resumida.append({
                "campeonato": jogo["league"]["name"],
                "casa": jogo["teams"]["home"]["name"],
                "fora": jogo["teams"]["away"]["name"],
                "hora_utc": jogo["fixture"]["date"]  # Ex: 2023-10-27T18:00:00+00:00
            })

        prompt = (
            "Você é o 'VAR do Lucro'. Organize a lista de partidas de futebol abaixo em um cronograma diário limpo e elegante.\n\n"
            "REGRAS DE CONVERSÃO E TRADUÇÃO:\n"
            "1. Agrupe as partidas estritamente por Campeonato/Liga.\n"
            "2. Converta o horário 'hora_utc' (que está em fuso UTC) para o Horário de Brasília (UTC-3). Mostre apenas as horas (ex: 11:00, 16:00, 20:30).\n"
            "3. Traduza obrigatoriamente todos os nomes de times, países e ligas para o Português do Brasil (ex: 'Brazil' vira 'Brasil', 'World Cup' vira 'Copa do Mundo').\n"
            "4. NÃO use asteriscos (*) em hipótese alguma na resposta final. Monte uma tabela textual bonita usando espaçamentos, quebras de linha e barras verticais se necessário.\n"
            "5. Adicione emojis esportivos ou bandeiras para deixar o visual atraente.\n\n"
            f"Lista de jogos do dia:\n{lista_resumida}"
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Erro ao gerar cronograma de jogos via IA: {e}")
        return "Erro ao construir o cronograma diário de partidas."

def gerar_relatorio_pre_jogo(fixture: Dict[str, Any]) -> str:
    """
    Gera o relatório compacto 'VAR do Lucro' avaliando mercados alternativos de alto valor
    como escanteios, cartões, faltas e posse.
    """
    try:
        client = obter_cliente_gemini()
        
        liga = fixture["league"]["name"]
        time_casa = fixture["teams"]["home"]["name"]
        time_fora = fixture["teams"]["away"]["name"]
        
        # Super prompt enxuto focado em síntese extrema e mercados alternativos de valor
        prompt = (
            f"Você é o 'VAR do Lucro', uma IA especialista em apostas esportivas de valor (+EV).\n"
            f"Faça uma análise ULTRA-RESUMIDA e DIRETA do confronto: {time_casa} vs {time_fora} pela liga '{liga}'.\n\n"
            
            f"INSTRUÇÃO DE MERCADOS ADICIONAIS (MUITO IMPORTANTE):\n"
            f"Além dos mercados comuns (Resultado e Gols), avalie mercados de Estatísticas alternativas se encontrar valor neles, tais como:\n"
            f"- ESCANTEIOS (Ex: Mais de 9.5 escanteios, Handicap de Cantos)\n"
            f"- CARTÕES (Ex: Mais de 4.5 cartões baseado no árbitro e rivalidade)\n"
            f"- FALTAS ou LATERAIS (Ex: Menos faltas baseado em times que jogam limpo)\n"
            f"Escolha as 2 opções de maior valor esperado (+EV) para indicar.\n\n"
            
            f"INSTRUÇÃO DE SÍNTESE:\n"
            f"Seja extremamente direto, enxuto e curto. Evite textos longos.\n"
            f"Traduza obrigatoriamente todos os nomes dos times, países e ligas para o Português do Brasil no relatório final.\n\n"
            
            f"Utilize a ferramenta de pesquisa do Google integrada para buscar dados reais de hoje sobre desfalques, árbitro, clima e médias de escanteios/cartões.\n\n"
            
            f"Siga estritamente o modelo de resposta abaixo, mantendo as justificativas muito curtas (máximo 1 linha):\n\n"
            
            f"🔍 RELATÓRIO DE INTELIGÊNCIA - VAR DO LUCRO\n"
            f"⚽ [Nome do Time Casa Traduzido] vs [Nome do Time Fora Traduzido]\n"
            f"🏆 [Nome da Liga Traduzido]\n"
            f"⏳ Começa em cerca de 1 hora!\n\n"
            
            f"📋 ANÁLISE DO CONFRONTO (Máximo de 3 linhas):\n"
            f"[Escreva em apenas 2 ou 3 linhas o fato crucial do jogo: desfalque, média alta de cartões/cantos, desgaste ou clima]\n\n"
            
            f"🎯 MERCADOS COM MAIOR VALOR (+EV):\n"
            f"1️⃣ [Mercado 1 - ex: Mais de 9.5 Escanteios / Handicap Gols / Ambas Marcam / Mais de 4.5 Cartões]\n"
            f"   • Justificativa (1 linha): [Motivo ultra-direto baseado em estatísticas, médias ou árbitro]\n"
            f"   • Confiança: [X%]\n"
            f"2️⃣ [Mercado 2 - ex: Diferente do mercado 1 (Ex: Cartões ou Resultado)]\n"
            f"   • Justificativa (1 linha): [Motivo ultra-direto]\n"
            f"   • Confiança: [X%]\n\n"
            
            f"⚠️ PRINCIPAL RISCO:\n"
            f"• [Escreva em apenas 1 linha o maior risco do jogo]\n\n"
            
            f"🛡️ GESTÃO E PSICOLOGIA:\n"
            f"• [1 conselho curto de Stake (1% a 3%) e controle emocional]\n\n"
            
            f"👉 Aposta sugerida? Confira na sua Casa favorita! Jogue com responsabilidade 🔞"
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
    if not API_FOOTBALL_KEY:
        print("Erro: API_FOOTBALL_KEY não foi configurada.")
        return None

    headers = {
        'x-rapidapi-host': 'v3.football.api-sports.io',
        'x-rapidapi-key': API_FOOTBALL_KEY
    }
    
    try:
        resposta_live = requests.get(f"{API_FOOTBALL_URL}/fixtures?live=all", headers=headers, timeout=15)
        jogos_ao_vivo = resposta_live.json().get("response", [])
        
        nome_time_min = nome_time.lower().strip()
        
        for jogo in jogos_ao_vivo:
            casa = jogo["teams"]["home"]["name"].lower()
            fora = jogo["teams"]["away"]["name"].lower()
            
            if nome_time_min in casa or nome_time_min in fora:
                fixture_id = jogo["fixture"]["id"]
                
                resposta_stats = requests.get(
                    f"{API_FOOTBALL_URL}/fixtures/statistics?fixture={fixture_id}", 
                    headers=headers, 
                    timeout=15
                )
                stats = resposta_stats.json().get("response", [])
                
                return {
                    "fixture": jogo,
                    "statistics": stats
                }
        return None
    except Exception as e:
        print(f"Erro ao tentar encontrar ou extrair estatísticas de jogo ao vivo para '{nome_time}': {e}")
        return None

def analisar_ao_vivo_e_formatar(dados_api: Dict[str, Any]) -> str:
    try:
        client = obter_cliente_gemini()
        
        fixture = dados_api["fixture"]
        liga = fixture["league"]["name"]
        time_casa = fixture["teams"]["home"]["name"]
        time_fora = fixture["teams"]["away"]["name"]
        tempo_minutos = fixture["fixture"]["status"]["elapsed"]
        gols_casa = fixture["goals"]["home"]
        gols_fora = fixture["goals"]["away"]
        estatisticas = dados_api["statistics"]

        prompt = (
            f"Analise o ritmo ofensivo do jogo ao vivo com as seguintes estatísticas:\n"
            f"Liga: {liga}\n"
            f"Confronto: {time_casa} v {time_fora}\n"
            f"Tempo: {tempo_minutos} minutos | Placar atual: {gols_casa} - {gols_fora}\n"
            f"Dados estatísticos: {estatisticas}\n\n"
            
            f"REGRA DE TRADUÇÃO OBRIGATÓRIA:\n"
            f"Traduza obrigatoriamente todos os nomes dos times, países e ligas para o Português do Brasil na mensagem final.\n"
            f"Por exemplo: 'Brazil' deve ser 'Brasil', 'Scotland' deve ser 'Escócia', 'Germany' deve ser 'Alemanha', 'World Cup' deve ser 'Copa do Mundo'.\n\n"
            
            f"REGRA DE HIPERLINKS DE CASAS DE APOSTAS (MUITO IMPORTANTE):\n"
            f"Na seção 'Confira nas casas', escolha de 1 a 2 casas de apostas da lista abaixo para recomendar (seja dinâmico na escolha).\n"
            f"Você deve formatar obrigatoriamente como link Markdown: [Nome da Casa](Link).\n"
            f"Use estritamente estes links oficiais listados (você pode sugerir outro se julgar pertinente usando sua URL padrão):\n"
            f"- Superbet: [Superbet](https://superbet.com)\n"
            f"- Bet365: [Bet365](https://www.bet365.com)\n"
            f"- EstrelaBet: [EstrelaBet](https://estrelabet.com)\n"
            f"- Novibet: [Novibet](https://novibet.com)\n"
            f"- Sportingbet: [Sportingbet](https://sportingbet.com)\n\n"
            
            f"Instruções:\n"
            f"1. Faça uma varredura veloz na internet (via pesquisa Google) para verificar se houve expulsões recentes (cartão vermelho) nesta partida.\n"
            f"2. Preencha e envie unicamente o modelo a seguir com os dados extraídos. Não altere os cabeçalhos das estatísticas:\n\n"
            
            f"💎 [Robô Over Gols - PREMIUM detectou uma chance quente!]\n\n"
            f"🏟 [Nome da Liga Traduzido]\n"
            f"⚽ [Nome do Time Casa Traduzido] v [Nome do Time Fora Traduzido]\n"
            f"🕐 {tempo_minutos} minutos\n"
            f"🔢 Placar do jogo: {gols_casa} - {gols_fora}\n\n"
            f"📊 Dados do jogo (Mandante - Visitante):\n"
            f"- Investidas ofensivas: [Ataques Perigosos do Mandante] - [Ataques Perigosos do Visitante]\n"
            f"- Escanteios: [Escanteios do Mandante] - [Escanteios do Visitante]\n"
            f"- Arremates: [Chutes Totais do Mandante] - [Chutes Totais do Visitante]\n"
            f"- Tentativas no alvo: [Chutes no Gol do Mandante] - [Chutes no Gol do Visitante]\n"
            f"- Controle da bola: [Posse do Mandante]% - [Posse do Visitante]%\n\n"
            f"🔥 Sinal: [Com base na pressão de finalizações, defina o sinal como 'Mais 0.5 Gols', 'Mais 1 Gol', ou 'Sem entrada recomendada']\n\n"
            f"↪ Confira nas casas:\n"
            f"🎲 Pegue na [Nome da Casa escolhida](Link_da_casa_escolhida)\n\n"
            f"Jogue com responsabilidade 🔞"
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
        print(f"Erro na análise de sinais ao vivo para {time_casa} vs {time_fora}: {e}")
        return "Desculpe, ocorreu uma instabilidade ao gerar o sinal de gols em tempo real."

# =====================================================================
# SEÇÃO 3: CONTROLE DE LIGAS E EXIBIÇÃO DE ELENCOS E ESTATÍSTICAS
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
    if not API_FOOTBALL_KEY:
        return []
    headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': API_FOOTBALL_KEY}
    try:
        resposta = requests.get(f"{API_FOOTBALL_URL}/leagues?search={termo_busca}", headers=headers, timeout=12)
        dados = resposta.json().get("response", [])
        return [{"id": item["league"]["id"], "nome": item["league"]["name"], "pais": item["country"]["name"]} for item in dados]
    except Exception as e:
        print(f"Erro ao buscar IDs: {e}")
        return []

def obter_estatisticas_time(team_id: int, league_id: int, season: int) -> Optional[Dict[str, Any]]:
    if not API_FOOTBALL_KEY:
        return None
    headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': API_FOOTBALL_KEY}
    try:
        resposta = requests.get(
            f"{API_FOOTBALL_URL}/teams/statistics?team={team_id}&league={league_id}&season={season}",
            headers=headers,
            timeout=12
        )
        return resposta.json().get("response")
    except Exception as e:
        print(f"Erro ao buscar estatísticas do time {team_id}: {e}")
        return None

def obter_elenco_time(team_id: int) -> List[Dict[str, Any]]:
    if not API_FOOTBALL_KEY:
        return []
    headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': API_FOOTBALL_KEY}
    try:
        resposta = requests.get(f"{API_FOOTBALL_URL}/players/squads?team={team_id}", headers=headers, timeout=12)
        dados = resposta.json().get("response", [])
        if dados:
            return dados[0].get("players", [])
        return []
    except Exception as e:
        print(f"Erro ao buscar elenco do time {team_id}: {e}")
        return []

def buscar_time_por_nome(nome_time: str) -> Optional[Dict[str, Any]]:
    if not API_FOOTBALL_KEY:
        return None
    headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': API_FOOTBALL_KEY}
    try:
        resposta = requests.get(f"{API_FOOTBALL_URL}/teams?search={nome_time}", headers=headers, timeout=12)
        dados = resposta.json().get("response", [])
        if dados:
            return dados[0]
        return None
    except Exception as e:
        print(f"Erro ao buscar time por nome: {e}")
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
