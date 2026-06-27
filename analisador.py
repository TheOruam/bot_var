# analisador.py
import os
import time
import requests
from datetime import datetime, timezone
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
# SEÇÃO 1: ANÁLISE PRÉ-JOGO (GERADOR DO "VAR DO LUCRO")
# =====================================================================

def obter_jogos_do_dia() -> List[Dict[str, Any]]:
    if not API_FOOTBALL_KEY:
        print("Erro: API_FOOTBALL_KEY não foi configurada.")
        return []
    
    headers = {
        'x-rapidapi-host': 'v3.football.api-sports.io',
        'x-rapidapi-key': API_FOOTBALL_KEY
    }
    hoje = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    try:
        resposta = requests.get(f"{API_FOOTBALL_URL}/fixtures?date={hoje}", headers=headers, timeout=15)
        todos_jogos = resposta.json().get("response", [])
        
        jogos_filtrados = [
            jogo for jogo in todos_jogos 
            if jogo["league"]["id"] in LIGAS_MONITORADAS
        ]
        
        print(f"Total de jogos hoje: {len(todos_jogos)} | Filtrados para monitoramento: {len(jogos_filtrados)}")
        return jogos_filtrados
        
    except Exception as e:
        print(f"Erro ao buscar partidas agendadas para o dia de hoje: {e}")
        return []

def gerar_relatorio_pre_jogo(fixture: Dict[str, Any]) -> str:
    try:
        client = obter_cliente_gemini()
        
        liga = fixture["league"]["name"]
        time_casa = fixture["teams"]["home"]["name"]
        time_fora = fixture["teams"]["away"]["name"]
        
        prompt = (
            f"Você é o analista-chefe da cabine do 'VAR do Lucro', uma IA especialista em apostas esportivas baseadas em Valor Esperado (+EV).\n"
            f"Sua missão é analisar o confronto entre {time_casa} (Mandante) e {time_fora} (Visitante) pela liga '{liga}'.\n\n"
            
            f"REGRA DE TRADUÇÃO OBRIGATÓRIA:\n"
            f"Traduza obrigatoriamente todos os nomes dos times, países e ligas para o Português do Brasil no relatório final.\n"
            f"Por exemplo: 'Brazil' deve ser 'Brasil', 'Scotland' deve ser 'Escócia', 'Germany' deve ser 'Alemanha', 'World Cup' deve ser 'Copa do Mundo'.\n\n"
            
            f"Utilize a ferramenta de pesquisa do Google integrada para buscar dados reais de hoje sobre:\n"
            f"- MANDO DE CAMPO E VIAGENS: Como é o rendimento do {time_fora} fora de casa? Houve desgaste de viagem recente?\n"
            f"- FORMA RECENTE: Resultados e comportamento ofensivo/defensivo dos últimos 5 a 6 jogos de cada equipe.\n"
            f"- DESFALQUES E LESÕES: Ausência de artilheiros, zagueiros titulares, capitães ou goleiros de última hora.\n"
            f"- MOTIVAÇÃO E CALENDÁRIO: Há desgaste físico? Algum time poupará titulares visando mata-mata?\n"
            f"- CONDIÇÕES CLIMÁTICAS E ARBITRAGEM: Gramado pesado por chuva? Perfil de cartões e faltas do árbitro escalado.\n"
            f"- CLIMA NO VESTIÁRIO E NARRATIVAS: Salários atrasados, crises internas, ou chance da 'Lei do Ex'.\n"
            f"- ANÁLISE DE MERCADO: Movimentação brusca das odds e comparação de valores justos (+EV).\n\n"
            
            f"Formate a resposta exatamente seguindo o modelo a seguir, sem desvios de estrutura:\n\n"
            
            f"🔍 RELATÓRIO DE INTELIGÊNCIA - VAR DO LUCRO\n"
            f"⚽ [Nome do Time Casa Traduzido] vs [Nome do Time Fora Traduzido]\n"
            f"🏆 [Nome da Liga Traduzido]\n"
            f"⏳ Começa em cerca de 1 hora!\n\n"
            
            f"📋 ANÁLISE DO CONFRONTO:\n"
            f"[Escreva um resumo analítico e objetivo focado nos desfalques, clima, vestiário, desgaste físico ou lei do ex identificados na pesquisa. Lembre-se de escrever em português correto, com os nomes dos times em português]\n\n"
            
            f"🎯 MERCADOS COM MAIOR VALOR (+EV):\n"
            f"1️⃣ [Nome do Mercado - Ex: Handicap Asiático / Total de Gols]\n"
            f"   • Análise: [Justificativa técnica baseada nas estatísticas encontradas]\n"
            f"   • Confiança: [X%]\n"
            f"2️⃣ [Segundo Mercado de Valor]\n"
            f"   • Análise: [Justificativa técnica baseada na forma/desfalques]\n"
            f"   • Confiança: [X%]\n\n"
            
            f"⚠️ PRINCIPAIS RISCOS DA OPERAÇÃO:\n"
            f"• [Identifique o principal risco que pode anular a nossa análise, como retranca excessiva, clima ou arbitragem rigorosa]\n\n"
            
            f"🛡️ CONSELHO DE GESTÃO E PSICOLÓGICO:\n"
            f"• [Forneça uma instrução clara de gestão de banca personalizada para esta partida (ex: sugerir Stake de 1% a 3% dependendo do risco), além de reforçar o controle emocional para não buscar greens de recuperação de forma desesperada]\n\n"
            
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
            f"🎲 Pegue na Superbet\n\n"
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
# SEÇÃO 3: CONTROLE DE LIGAS E VARREDURA AUTOMÁTICA/MANUAL
# =====================================================================

LIGAS_MONITORADAS = [71, 39, 140, 2]
JOGOS_ANALISADOS = set()

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

def verificar_e_enviar_pre_jogos(bot) -> int:
    """
    Varre os jogos do dia e envia a análise automaticamente 
    para o tópico correto se o jogo começar em cerca de 1 hora.
    Retorna o número de relatórios enviados de forma bem-sucedida.
    """
    global JOGOS_ANALISADOS
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    topico_pre_jogo = os.getenv("TOPICO_PRE_JOGO")
    
    if not chat_id or not topico_pre_jogo:
        print("Aviso: CHAT_ID ou TOPICO_PRE_JOGO não configurado.")
        return 0

    print("Verificando jogos agendados para as próximas horas...")
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

        # Dispara quando faltar entre 50 e 70 minutos para o jogo começar
        if 50 <= minutos_para_comecar <= 70:
            time_casa = jogo["teams"]["home"]["name"]
            time_fora = jogo["teams"]["away"]["name"]
            print(f"Iniciando análise pré-jogo automática para: {time_casa} vs {time_fora}")
            
            try:
                relatorio = gerar_relatorio_pre_jogo(jogo)
                
                # Envia focado especificamente na sala de Pré-Jogo
                bot.send_message(
                    chat_id=chat_id,
                    text=relatorio,
                    message_thread_id=int(topico_pre_jogo)
                )
                
                JOGOS_ANALISADOS.add(fixture_id)
                enviados += 1
                time.sleep(2)
            except Exception as e:
                print(f"Falha ao enviar relatório automático para {time_casa} vs {time_fora}: {e}")
                
    return enviados
