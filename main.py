import os
import time
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask
import telebot
from comandos import registrar_comandos
from analisador import obter_jogos_do_dia, gerar_relatorio_pre_jogo

# Inicialização do Servidor Web Flask (para o Render/Koyeb manter ativo)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Online e Operando com Sucesso!", 200

# Inicialização do Bot do Telegram
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_CANAL = os.getenv("TELEGRAM_CHAT_ID")  # ID do canal/grupo onde o bot postará os sinais automáticos

if not TOKEN:
    raise ValueError("A variável de ambiente 'TELEGRAM_TOKEN' não está configurada.")

bot = telebot.TeleBot(TOKEN)
registrar_comandos(bot)

# ==========================================
# AGENDADOR AUTOMÁTICO (PRÉ-JOGO - 1 HORA ANTES)
# ==========================================

# Conjunto de controle para garantir que não enviaremos análises duplicadas do mesmo jogo
jogos_analisados = set()

def verificar_e_enviar_pre_jogos():
    """
    Varre os jogos do dia de tempos em tempos e envia a análise 
    caso o jogo comece em aproximadamente 1 hora (entre 50 e 70 minutos).
    """
    global jogos_analisados
    
    if not CHAT_ID_CANAL:
        print("Aviso: 'TELEGRAM_CHAT_ID' não está configurado. O agendador automático está desativado.")
        return

    print("Verificando jogos agendados para as próximas horas...")
    jogos = obter_jogos_do_dia()
    agora = datetime.now(timezone.utc)

    for jogo in jogos:
        fixture_id = jogo["fixture"]["id"]
        
        # Ignora se o jogo já foi analisado hoje
        if fixture_id in jogos_analisados:
            continue
            
        # Pega a data/hora de início do jogo convertida para UTC
        data_jogo_str = jogo["fixture"]["date"]
        # Exemplo de data da API: 2023-10-27T15:00:00+00:00
        data_jogo = datetime.fromisoformat(data_jogo_str.replace("Z", "+00:00"))

        # Calcula a diferença de tempo entre o momento atual e o início do jogo
        diferenca_tempo = data_jogo - agora
        minutos_para_comecar = diferenca_tempo.total_seconds() / 60

        # Se o jogo começa entre 50 e 70 minutos (janela de 1 hora antes)
        if 50 <= minutos_para_comecar <= 70:
            time_casa = jogo["teams"]["home"]["name"]
            time_fora = jogo["teams"]["away"]["name"]
            print(f"Iniciando análise pré-jogo automatizada para: {time_casa} vs {time_fora}")
            
            try:
                # Gera o relatório completo
                relatorio = gerar_relatorio_pre_jogo(jogo)
                
                # Envia o relatório de forma automática para o seu canal/grupo
                bot.send_message(CHAT_ID_CANAL, relatorio)
                
                # Marca o ID do jogo como enviado para não repetir
                jogos_analisados.add(fixture_id)
                time.sleep(2)  # Evita flood de requisições no Telegram
            except Exception as e:
                print(f"Falha ao enviar relatório automático para {time_casa} vs {time_fora}: {e}")

def tarefa_agendada_loop():
    """
    Loop que roda continuamente a cada 10 minutos verificando 
    se existem jogos na janela de tempo de 1 hora antes.
    """
    # Aguarda 30 segundos ao iniciar o script para dar tempo das conexões subirem
    time.sleep(30)
    
    while True:
        try:
            verificar_e_enviar_pre_jogos()
        except Exception as e:
            print(f"Erro no loop do agendador automático: {e}")
        
        # Aguarda 10 minutos para realizar a próxima varredura
        time.sleep(600)

# ==========================================
# INICIALIZAÇÃO EM PARALELO (THREADS)
# ==========================================

def rodar_servidor_web():
    """Roda o Flask na porta definida pela hospedagem (padrão 8080 ou 10000)."""
    porta = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)

if __name__ == "__main__":
    # 1. Inicia o servidor web Flask em uma Thread (Processo Paralelo)
    thread_flask = threading.Thread(target=rodar_servidor_web, daemon=True)
    thread_flask.start()
    print("Servidor Web Flask iniciado com sucesso.")

    # 2. Inicia o agendador de análise automática de 1 hora em outra Thread
    thread_agendador = threading.Thread(target=tarefa_agendada_loop, daemon=True)
    thread_agendador.start()
    print("Agendador automático pré-jogo iniciado com sucesso.")

    # 3. Executa o loop principal do Telegram (Isso segura a execução do main)
    print("Iniciando escuta do Bot do Telegram (Infinity Polling)...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Falha crítica no polling do Bot: {e}")
