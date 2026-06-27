# main.py
import os
import time
import threading
from flask import Flask
import telebot
from comandos import registrar_comandos
from analisador import verificar_e_enviar_pre_jogos

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Online e Operando com Sucesso!", 200

# Inicialização do Bot
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("A variável de ambiente 'TELEGRAM_TOKEN' não está configurada.")

bot = telebot.TeleBot(TOKEN)
registrar_comandos(bot)

# ==========================================
# AGENDADOR AUTOMÁTICO (PRÉ-JOGO)
# ==========================================

def tarefa_agendada_loop():
    time.sleep(30)
    while True:
        try:
            # Chama a função unificada de varredura
            verificar_e_enviar_pre_jogos(bot)
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
