import os
import telebot
from telebot.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
import analisador

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
bot = telebot.TeleBot(TOKEN)

# Identificadores de salas/tópicos (Vêm das variáveis de ambiente)
TOPICO_PRE_JOGO = os.getenv("TOPICO_PRE_JOGO")
TOPICO_AO_VIVO = os.getenv("TOPICO_AO_VIVO")
TOPICO_RESENHA = os.getenv("TOPICO_RESENHA")
TOPICO_ADMINS = os.getenv("TOPICO_ADMINS")
CHAT_ID_GERAL = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

def obter_id_topico(message):
    """Retorna o ID do tópico (thread) atual da mensagem de forma limpa."""
    if message.reply_to_message and message.reply_to_message.forum_topic_created_metadata:
        return str(message.message_thread_id)
    if hasattr(message, 'message_thread_id'):
        return str(message.message_thread_id)
    return None

def eh_admin(message):
    """Verifica se o usuário é administrador do chat ou se a mensagem veio do tópico de admins."""
    topico_atual = obter_id_topico(message)
    if topico_atual == TOPICO_ADMINS:
        return True
    try:
        status = bot.get_chat_member(message.chat.id, message.from_user.id).status
        return status in ["creator", "administrator"]
    except Exception:
        return False

# ==========================================
# INTERAÇÕES DO ADMIN E DE COMUNIDADE
# ==========================================

@bot.message_handler(commands=['bomdia'])
def cmd_bomdia(message):
    prompt = "Crie uma mensagem divertida de bom dia para o grupo de apostadores e analistas, incentivando a lucrar hoje."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

@bot.message_handler(commands=['bemvindo'])
def cmd_bemvindo(message):
    prompt = "Gere uma saudação divertida e acolhedora para um novo membro que acabou de entrar no grupo VAR do Lucro."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

@bot.message_handler(commands=['green'])
def cmd_green(message):
    prompt = "Comemore um GREEN espetacular de forma enérgica e provocativa, mantendo a seriedade analítica do VAR do Lucro."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

@bot.message_handler(commands=['red'])
def cmd_red(message):
    prompt = "Gere uma mensagem analítica e resiliente sobre um RED que aconteceu, destacando que a gestão de banca e longo prazo nos salvará."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

@bot.message_handler(commands=['resenha'])
def cmd_resenha(message):
    prompt = "Inicie um debate divertido chamando a comunidade para debater as melhores entradas do mercado para as próximas horas."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.reply_to(message, resposta, parse_mode="HTML")

# Acolhimento Automático de Membros que entram no grupo
@bot.message_handler(content_types=['new_chat_members'])
def acolher_membro_automatico(message):
    # Envia a mensagem no tópico correto de Resenha/Bate-papo se estiver configurado
    thread_id = int(TOPICO_RESENHA) if TOPICO_RESENHA else None
    prompt = "Dê as boas-vindas calorosas a um novo membro no canal VAR do Lucro, sem utilizar asteriscos."
    resposta = analisador.perguntar_ao_gemini(prompt)
    bot.send_message(message.chat.id, resposta, message_thread_id=thread_id, parse_mode="HTML")

# ==========================================
# COMANDO DO CRONOGRAMA DIÁRIO
# ==========================================

@bot.message_handler(commands=['cronograma'])
def cmd_cronograma(message):
    # Apenas administradores podem acionar o cronograma manual na sala Admin
    if not eh_admin(message):
        bot.reply_to(message, "Apenas administradores podem rodar este comando.")
        return

    enviar_cronograma_diario()

def enviar_cronograma_diario():
    """Gera o cronograma formatado e envia no Tópico Pré-Jogo."""
    jogos = analisador.obter_jogos_do_dia(forcar=True)
    if not jogos:
        texto = "⚽ <b>VAR DO LUCRO - CRONOGRAMA DIÁRIO</b>\n\nNenhuma partida monitorada para o dia de hoje."
        bot.send_message(CHAT_ID_GERAL, texto, message_thread_id=int(TOPICO_PRE_JOGO) if TOPICO_PRE_JOGO else None, parse_mode="HTML")
        return

    mensagens = ["⚽ <b>VAR DO LUCRO - CRONOGRAMA DIÁRIO</b>\n──────────"]
    for j in jogos:
        # Transforma o horário UTC em horário de Brasília para exibição
        try:
            dt_utc = datetime.fromisoformat(j["data_utc"].replace("Z", "+00:00"))
            dt_br = dt_utc.astimezone(timezone(timedelta(hours=-3)))
            hora_exibida = dt_br.strftime("%H:%M")
        except Exception:
            hora_exibida = "Horário Indefinido"

        card = (
            f"⏰ Horário: <b>{hora_exibida}</b> (Brasília)\n"
            f"🏆 Competição: <i>{j['liga']}</i> ({j['pais']})\n"
            f"🏟️ Estádio: {j['estadio']}\n"
            f"⚔️ Partida: <b>{j['mandante']}</b> x <b>{j['visitante']}</b>\n"
            f"──────────"
        )
        mensagens.append(card)

    texto_final = "\n".join(mensagens)
    bot.send_message(CHAT_ID_GERAL, texto_final, message_thread_id=int(TOPICO_PRE_JOGO) if TOPICO_PRE_JOGO else None, parse_mode="HTML")

# ==========================================
# COMANDO DE SINAL AO VIVO (/aovivo)
# ==========================================

@bot.message_handler(commands=['aovivo'])
def cmd_aovivo(message):
    partes = message.text.split(maxsplit=1)
    if len(partes) < 2:
        bot.reply_to(message, "<b>Entrada Inválida</b>\nUse o formato: /aovivo NOME_DO_TIME", parse_mode="HTML")
        return

    termo = partes[1]
    msg_carregando = bot.reply_to(message, "<i>Consultando dados em tempo real...</i>", parse_mode="HTML")

    try:
        dados = analisador.consultar_dados_ao_vivo(termo)
        if not dados:
            bot.edit_message_text(
                "❌ <b>Partida Não Encontrada</b>\nNão foi identificado nenhum jogo ao vivo ocorrendo agora para o time informado. Certifique-se de que a equipe está em campo neste exato momento.",
                chat_id=message.chat.id,
                message_id=msg_carregando.message_id,
                parse_mode="HTML"
            )
            return

        # Montagem do layout tático do placar ao vivo utilizando barras proporcionais em Python
        layout = (
            f"🏟️ <b>{dados['liga']}</b>\n"
            f"⚽ <b>{dados['mandante']} {dados['gols_m']}</b> x <b>{dados['gols_v']} {dados['visitante']}</b>\n"
            f"⏱️ Tempo: {dados['tempo']}' ({dados['status']})\n\n"
            f"📊 <b>ESTATÍSTICAS EM TEMPO REAL:</b>\n"
            f"🔵 {dados['mandante']} | 🔴 {dados['visitante']}\n\n"
            f"🔹 Posse de Bola: {dados['posse_m']}% vs {dados['posse_v']}%\n"
            f"{dados['barra_posse']}\n"
            f"🔹 Chutes ao Gol: {dados['cg_m']} vs {dados['cg_v']}\n"
            f"{dados['barra_chutes']}\n"
            f"🔹 Ataques Totais: {dados['atq_m']} vs {dados['atq_v']}\n"
            f"{dados['barra_ataques']}\n"
            f"🔹 Ataques Perigosos: {dados['atqp_m']} vs {dados['atqp_v']}\n"
            f"{dados['barra_perigo']}\n"
            f"🔹 Escanteios: {dados['esc_m']} vs {dados['esc_v']}\n"
            f"{dados['barra_escanteios']}\n\n"
            f"🤖 <b>PROCESSANDO ANÁLISE DE IA...</b>"
        )

        bot.edit_message_text(
            layout,
            chat_id=message.chat.id,
            message_id=msg_carregando.message_id,
            parse_mode="HTML"
        )

        # Envia os dados para a IA estruturar o sinal de Over Gols ou Entrada +EV
        prompt_ia = (
            f"Analise esta partida ao vivo no minuto {dados['tempo']}. "
            f"Time Mandante: {dados['mandante']} ({dados['gols_m']} gols, posse {dados['posse_m']}%, ataques perigosos {dados['atqp_m']}, escanteios {dados['esc_m']}). "
            f"Time Visitante: {dados['visitante']} ({dados['gols_v']} gols, posse {dados['posse_v']}%, ataques perigosos {dados['atqp_v']}, escanteios {dados['esc_v']}). "
            "Gere uma recomendação de aposta em tempo real (+EV) divertida e analítica (ex: Over Gols, Ambas Marcam, Escanteios, Back Mandante/Visitante) fundamentada nestas estatísticas. "
            "Adicione um link no fim direcionando o usuário de maneira natural para a Superbet usando este formato estrito: <a href='https://superbet.com'>Aproveitar Oportunidade na Superbet</a>"
        )

        analise_ia = analisador.perguntar_ao_gemini(prompt_ia)

        layout_final = layout.replace("🤖 <b>PROCESSANDO ANÁLISE DE IA...</b>", f"🤖 <b>SINAL DO VAR DO LUCRO:</b>\n\n{analise_ia}")
        
        bot.edit_message_text(
            layout_final,
            chat_id=message.chat.id,
            message_id=msg_carregando.message_id,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"[ERRO AO VIVO] Falha no comando ao vivo: {str(e)}")
        bot.edit_message_text(
            "❌ <b>Erro Interno</b>\nHouve uma falha inesperada ao obter e analisar as estatísticas do jogo.",
            chat_id=message.chat.id,
            message_id=msg_carregando.message_id,
            parse_mode="HTML"
        )

# ==========================================
# PAINEL DO TIME (WEB APP TELEGRAM)
# ==========================================

@bot.message_handler(commands=['painel'])
def cmd_painel(message):
    partes = message.text.split(maxsplit=1)
    if len(partes) < 2:
        bot.reply_to(message, "<b>Entrada Inválida</b>\nUse o formato: /painel NOME_DO_TIME", parse_mode="HTML")
        return

    time_busca = partes[1]
    
    # Valida se a URL do Web App foi definida
    if not WEBHOOK_URL:
        bot.reply_to(message, "Configuração de painel pendente (WEBHOOK_URL não configurada).")
        return

    # Gera link parametrizado do Web App
    url_painel = f"{WEBHOOK_URL}/painel?time={time_busca}"
    
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton(text="Abrir Painel Estatístico", web_app=WebAppInfo(url=url_painel))
    markup.add(btn)

    bot.reply_to(
        message,
        f"📊 <b>Painel Interativo do {time_busca}</b>\n\nClique no botão abaixo para carregar os gráficos de desempenho e o elenco em tempo real diretamente da nuvem.",
        reply_markup=markup,
        parse_mode="HTML"
    )

# ==========================================
# BALANÇO E AUDITORIA DO DIA (/resumo)
# ==========================================

@bot.message_handler(commands=['resumo'])
def cmd_resumo(message):
    if not eh_admin(message):
        bot.reply_to(message, "Apenas administradores podem acionar o resumo do dia.")
        return

    msg_auditoria = bot.reply_to(message, "<i>Coletando resultados e auditando palpites...</i>", parse_mode="HTML")

    try:
        jogos = analisador.obter_jogos_do_dia()
        if not jogos:
            bot.edit_message_text(
                "Nenhum jogo cadastrado no cache de hoje para consolidação.",
                chat_id=message.chat.id,
                message_id=msg_auditoria.message_id,
                parse_mode="HTML"
            )
            return

        relatorio_jogos = []
        for j in jogos:
            relatorio_jogos.append(
                f"- {j['mandante']} {j['gols_mandante']} x {j['gols_visitante']} {j['visitante']} (Status: {j['status']}, Liga: {j['liga']})"
            )
        
        relatorio_texto = "\n".join(relatorio_jogos)

        prompt_ia = (
            f"Abaixo estão os resultados das partidas de hoje:\n{relatorio_texto}\n\n"
            "Atue como o Auditor Estatístico do VAR do Lucro. Faça um consolidado divertido "
            "e direto determinando quais partidas terminaram em GREEN (🟢) para opções comuns como Over 1.5, Over 2.5 "
            "ou Ambas Marcam baseado estritamente nos gols acima, e quais deram RED (🔴). Encerre com a nossa "
            "frase de efeito motivadora sem utilizar asteriscos."
        )

        resumo_gerado = analisador.perguntar_ao_gemini(prompt_ia)
        
        # Posta o balanço final diretamente na sala do Pré-Jogo para a comunidade
        bot.send_message(
            CHAT_ID_GERAL,
            f"🏆 <b>VAR DO LUCRO - AUDITORIA DE RESULTADOS</b>\n\n{resumo_gerado}",
            message_thread_id=int(TOPICO_PRE_JOGO) if TOPICO_PRE_JOGO else None,
            parse_mode="HTML"
        )

        bot.edit_message_text(
            "Consolidado diário enviado com sucesso na sala Pré-Jogo!",
            chat_id=message.chat.id,
            message_id=msg_auditoria.message_id,
            parse_mode="HTML"
        )

    except Exception as e:
        print(f"[ERRO RESUMO] Falha ao auditar resumo: {str(e)}")
        bot.edit_message_text(
            "Erro ao realizar a auditoria dos palpites de hoje.",
            chat_id=message.chat.id,
            message_id=msg_auditoria.message_id,
            parse_mode="HTML"
        )