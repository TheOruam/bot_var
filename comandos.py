# comandos.py
import os
import random
import requests
from telebot import TeleBot
from deep_translator import GoogleTranslator
from analisador import buscar_jogo_ao_vivo_por_time, analisar_ao_vivo_e_formatar, obter_jogos_do_dia, gerar_relatorio_pre_jogo, obter_cliente_gemini

# Captura os IDs das salas do ambiente (padrão 0 caso não configurados)
ID_PRE_JOGO = int(os.getenv("TOPICO_PRE_JOGO", "0"))
ID_AO_VIVO = int(os.getenv("TOPICO_AO_VIVO", "0"))
ID_RESENHA = int(os.getenv("TOPICO_RESENHA", "0"))
ID_ADMINS = int(os.getenv("TOPICO_ADMINS", "0"))

def eh_admin(bot: TeleBot, message) -> bool:
    """Verifica se o remetente é administrador do grupo."""
    if message.chat.type == "private":
        return True
    try:
        status_membro = bot.get_chat_member(message.chat.id, message.from_user.id).status
        return status_membro in ["administrator", "creator"]
    except Exception as e:
        print(f"Erro ao verificar permissões de admin: {e}")
        return False

def verificar_sala(message, id_sala_permitida: int) -> bool:
    """
    Compara o ID do tópico de onde veio a mensagem com o ID da sala permitida.
    Permite a execução em chats privados para facilitar testes.
    """
    if message.chat.type == "private":
        return True
    
    thread_id = message.message_thread_id
    if thread_id is None:
        thread_id = 0
        
    return int(thread_id) == id_sala_permitida

def traduzir_busca_para_ingles(termo: str) -> str:
    """
    Traduz de forma inteligente o termo digitado em Português para o Inglês.
    Ex: 'Brasil' -> 'Brazil', 'Escócia' -> 'Scotland'.
    Evita falhas de busca na API-Football.
    """
    try:
        traducao = GoogleTranslator(source='pt', target='en').translate(termo)
        print(f"Busca original: '{termo}' | Traduzido para API: '{traducao}'")
        return traducao
    except Exception as e:
        print(f"Erro na tradução pré-busca: {e}")
        return termo

def registrar_comandos(bot: TeleBot):
    """Registra todos os comandos e faz a triagem das salas de destino."""

    @bot.message_handler(commands=['start', 'ajuda'])
    def enviar_ajuda(message):
        texto = (
            "💎 Central de Inteligência Esportiva 💎\n\n"
            "Cada comando possui sua sala específica:\n"
            "• Use o comando /prejogo somente na sala Pré-Jogo.\n"
            "• Use o comando /aovivo somente na sala de Sinais Ao Vivo."
        )
        bot.reply_to(message, texto)

    # =====================================================================
    # COMANDO: PRÉ-JOGO (APENAS NA SALA PRÉ-JOGO)
    # =====================================================================
    @bot.message_handler(commands=['prejogo'])
    def comando_pre_jogo(message):
        if not verificar_sala(message, ID_PRE_JOGO):
            bot.reply_to(message, "⚠️ Este comando so pode ser utilizado na sala Pré-Jogo.")
            return

        args = message.text.replace('/prejogo', '').strip()
        if not args:
            bot.reply_to(message, "⚠️ Digite o nome do time. Exemplo: /prejogo Flamengo")
            return
            
        bot.reply_to(message, f"🔍 Traduzindo e buscando cronograma de hoje para '{args}'...")
        
        args_ingles = traduzir_busca_para_ingles(args)
        
        jogos_hoje = obter_jogos_do_dia()
        jogo_encontrado = None
        args_min = args_ingles.lower().strip()
        
        for jogo in jogos_hoje:
            casa = jogo["teams"]["home"]["name"].lower()
            fora = jogo["teams"]["away"]["name"].lower()
            if args_min in casa or args_min in fora:
                jogo_encontrado = jogo
                break
                
        if not jogo_encontrado:
            bot.send_message(
                chat_id=message.chat.id, 
                text=f"❌ Não encontrei nenhuma partida para hoje com o nome '{args}'.",
                message_thread_id=message.message_thread_id
            )
            return
            
        bot.send_message(
            chat_id=message.chat.id, 
            text="🧠 Gerando Relatório de Inteligência VAR do Lucro...",
            message_thread_id=message.message_thread_id
        )
        relatorio = gerar_relatorio_pre_jogo(jogo_encontrado)
        bot.send_message(
            chat_id=message.chat.id, 
            text=relatorio,
            message_thread_id=message.message_thread_id
        )

    # =====================================================================
    # COMANDO: AO VIVO (APENAS NA SALA SINAIS AO VIVO)
    # =====================================================================
    @bot.message_handler(commands=['aovivo'])
    def comando_ao_vivo(message):
