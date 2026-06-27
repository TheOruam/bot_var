# main.py
import os
import time
import threading
from datetime import datetime, timezone
from flask import Flask
import telebot
from comandos import registrar_comandos
from analisador import obter_jogos_do_dia, gerar_relatorio_pre_jogo

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Online e Operando com Sucesso!", 200

# Inicialização de Variáveis de Ambiente e Bot
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_GRUPO = os.getenv("TELEGRAM_CHAT_ID")  # ID do grupo (começa com -100)
TOPICO_PRE_JOGO = os.getenv("TOPICO_PRE_JOGO")  # ID numérico da sala Pré-Jogo

if not TOKEN:
    raise ValueError("A variável de ambiente 'TELEGRAM_TOKEN' não está configurada.")

bot = telebot.TeleBot(TOKEN)
registrar_comandos(bot)

# ==========================================
# AGENDADOR AUTOMÁTICO (PRÉ-JOGO)
# ==========================================

jogos_analisados = set()

def verificar_e_enviar_pre_jogos():
    """
    Varre os jogos do dia e envia a análise automaticamente 
    para o tópico correto se o jogo começar em cerca de 1 hora.
    """
    global jogos_analisados
    
    if not CHAT_ID_GRUPO or not TOPICO_PRE_JOGO:
        print("Aviso: CHAT_ID ou TOPICO_PRE_JOGO não configurado. Agendador inativo.")
        return

    print("Verificando jogos agendados para as próximas horas...")
    jogos = obter_jogos_do_dia()
    agora = datetime.now(timezone.utc)

    for jogo in jogos:
        fixture_id = jogo["fixture"]["id"]
        
        if fixture_id in jogos_analisados:
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
                
                # ENVIO DIRECIONADO: Enviado para o Grupo, porém focado especificamente na sala Pré-Jogo (thread_id)
                bot.send_message(
                    chat_id=CHAT_ID_GRUPO,
                    text=relatorio,
                    message_thread_id=int(TOPICO_PRE_JOGO)
                )
                
                jogos_analisados.add(fixture_id)
                time.sleep(2)
            except Exception as e:
                print(f"Falha ao enviar relatório automático para {time_casa} vs {time_fora}: {e}")

def tarefa_agendada_loop():
    time.sleep(30)
    while True:
        try:
            verificar_e_enviar_pre_jogos()
        except Exception as e:
            print(f"Erro no loop do agendador automático: {e}")
        time.sleep(600)

# ==========================================
# INICIALIZAÇÃO
# ==========================================

def rodar_servidor_web():
    porta = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)

if __name__ == "__main__":
    thread_flask = threading.Thread(target=rodar_servidor_web, daemon=True)
    thread_flask.start()

    thread_agendador = threading.Thread(target=tarefa_agendada_loop, daemon=True)
    thread_agendador.start()

    print("Iniciando escuta do Bot do Telegram...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Falha crítica no polling do Bot: {e}")
