# comandos.py
import os
import random
import requests
import time
from telebot import TeleBot
from deep_translator import GoogleTranslator
from analisador import buscar_jogo_ao_vivo_por_time, analisar_ao_vivo_e_formatar, obter_jogos_do_dia, gerar_relatorio_pre_jogo, obter_cliente_gemini, buscar_time_por_nome

# Captura os IDs das salas do ambiente (padrão 0 caso não configurados)
ID_PRE_JOGO = int(os.getenv("TOPICO_PRE_JOGO", "0"))
ID_AO_VIVO = int(os.getenv("TOPICO_AO_VIVO", "0"))
ID_RESENHA = int(os.getenv("TOPICO_RESENHA", "0"))
ID_ADMINS = int(os.getenv("TOPICO_ADMINS", "0"))

# Guarda o cronômetro do comando supremo de recache em memória
ULTIMO_RECACHE_TIME = 0.0

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
    """Compara o ID do tópico de onde veio a mensagem com o ID da sala permitida."""
    if message.chat.type == "private":
        return True
    thread_id = message.message_thread_id
    if thread_id is None:
        thread_id = 0
    return int(thread_id) == id_sala_permitida

def traduzir_busca_para_ingles(termo: str) -> str:
    """Traduz termos em português para inglês para compatibilidade com seleções."""
    try:
        traducao = GoogleTranslator(source='pt', target='en').translate(termo)
        print(f"Busca original: '{termo}' | Traduzido para API: '{traducao}'")
        return traducao
    except Exception as e:
        print(f"Erro na tradução pré-busca: {e}")
        return termo

def gerar_texto_interativo_ia(prompt: str) -> str:
    """Gera textos criativos e inéditos em tempo real usando o Google Gemini 2.5 Flash."""
    try:
        client = obter_cliente_gemini()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Erro ao gerar text interativo com a IA: {e}")
        return "Erro temporário de conexão com a cabine do VAR. Tente novamente em instantes."

def registrar_comandos(bot: TeleBot):
    """Registra todos os comandos e faz a triagem das salas de destino."""

    @bot.message_handler(commands=['start', 'ajuda'])
    def enviar_ajuda(message):
        # Se for um Admin digitando na Mesa dos Admins, mostra a ajuda avançada de controle
        if eh_admin(bot, message) and verificar_sala(message, ID_ADMINS):
            ajuda_admin = (
                "💎 PAINEL DE CONTROLE DO OPERADOR (ADMINS) 💎\n\n"
                "Aqui esta o manual com todos os comandos criados e suas funcoes:\n\n"
                "📌 COMANDOS PUBLICOS (Disponiveis para membros):\n"
                "• /prejogo <time>: Manda o relatorio VAR do Lucro. (Somente na sala Pre-Jogo)\n"
                "• /aovivo <time>: Manda o sinal de Over Gols. (Somente na sala de Sinais Ao Vivo)\n\n"
                "📌 INTERACOES DO ADMIN (Qualquer uma das 4 salas):\n"
                "• /bomdia: Envia mensagem animada sobre regras de ouro e gestao.\n"
                "• /bemvindo: Envia recepcao do VAR (disparado auto para novos membros na Resenha).\n"
                "• /green: Alerta festivo para comemorar acertos.\n"
                "• /red: Alerta tecnico focado em gestao e psicologia pos-red.\n"
                "• /resenha: Sorteia uma curiosidade bizarra de futebol.\n\n"
                "📌 COMANDOS CRITICOS E APIS (Apenas na sala Mesa dos Admins):\n"
                "• /update: Faz auto-diagnostico das conexoes do Gemini e API de Futebol.\n"
                "• /ids <busca>: Pesquisa e retorna os IDs corretos de ligas na API.\n"
                "• /addliga <ID>: Adiciona um campeonato ao monitoramento ativo.\n"
                "• /remliga <ID>: Remove um campeonato do monitoramento.\n"
                "• /verligas: Mostra os IDs das ligas monitoradas no momento.\n"
                "• /scan: Força a varredura de jogos para a proxima hora imediatamente.\n"
                "• /cronograma: Forca a geracao e envio da tabela de jogos de hoje para a sala Pre-Jogo.\n"
                "• /painel <time>: Abre o painel visual com graficos e elenco do time.\n"
                "• /resumo: Coleta placares e estatísticas de hoje e gera um balanço de fechamento com Greens.\n"
                "• /recache: Força o bot a buscar dados atualizados na API (Dono apenas)."
            )
            bot.send_message(
                chat_id=message.chat.id, 
                text=ajuda_admin,
                message_thread_id=message.message_thread_id
            )
            return

        # Ajuda padrão para membros nas outras salas
        texto_membro = (
            "💎 Central de Inteligência Esportiva 💎\n\n"
            "Cada comando possui sua sala específica:\n"
            "• Use o comando /prejogo somente na sala Pré-Jogo.\n"
            "• Use o comando /aovivo somente na sala de Sinais Ao Vivo."
        )
        bot.reply_to(message, texto_membro)

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
            
            # Cruzamento duplo de segurança (Português ou Inglês)
            if args.lower().strip() in casa or args.lower().strip() in fora or args_min in casa or args_min in fora:
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
        
        # SISTEMA DE SEGURANÇA CONTRA MENSAGENS LONGAS (FATIADOR DE CARACTERE) [1]
        limite_telegram = 4000
        if len(relatorio) <= limite_telegram:
            bot.send_message(
                chat_id=message.chat.id, 
                text=relatorio, 
                message_thread_id=message.message_thread_id
            )
        else:
            # Fatia a resposta do Gemini em blocos menores para o Telegram aceitar [1]
            tamanho_fatia = 3900
            partes = [relatorio[i:i+tamanho_fatia] for i in range(0, len(relatorio), tamanho_fatia)]
            for idx, parte in enumerate(partes):
                bot.send_message(
                    chat_id=message.chat.id,
                    text=f"📋 [Análise - Parte {idx+1}/{len(partes)}]\n\n{parte}",
                    message_thread_id=message.message_thread_id
                )
                time.sleep(1) # Pausa de 1 segundo de segurança

    # =====================================================================
    # COMANDO: AO VIVO (APENAS NA SALA SINAIS AO VIVO)
    # =====================================================================
    @bot.message_handler(commands=['aovivo'])
    def comando_ao_vivo(message):
        if not verificar_sala(message, ID_AO_VIVO):
            bot.reply_to(message, "⚠️ Este comando so pode ser utilizado na sala de Sinais Ao Vivo.")
            return

        args = message.text.replace('/aovivo', '').strip()
        if not args:
            bot.reply_to(message, "⚠️ Digite o nome do time. Exemplo: /aovivo Real Madrid")
            return
        
        bot.reply_to(message, f"🔍 Procurando partida ao vivo para '{args}'...")
        
        args_original = args.strip()
        args_ingles = traduzir_busca_para_ingles(args)
        
        # Passa o nome original e o traduzido para a busca ao vivo inteligente
        dados_jogo = buscar_jogo_ao_vivo_por_time(args_original, args_ingles)
        
        if not dados_jogo:
            bot.send_message(
                chat_id=message.chat.id, 
                text=f"❌ Nenhuma partida ao vivo encontrada para '{args}' no momento.",
                message_thread_id=message.message_thread_id
            )
            return
            
        bot.send_message(
            chat_id=message.chat.id, 
            text="📊 Partida encontrada! Calculando probabilidades...",
            message_thread_id=message.message_thread_id
        )
        analise_final = analisar_ao_vivo_e_formatar(dados_jogo)
        bot.send_message(
            chat_id=message.chat.id, 
            text=analise_final,
            message_thread_id=message.message_thread_id,
            parse_mode="Markdown"
        )

    # =====================================================================
    # COMANDOS DE ADMINS - GRUPO 1: APENAS NA "MESA DOS ADMINS"
    # =====================================================================
    @bot.message_handler(commands=['update', 'addliga', 'remliga', 'verligas', 'ids', 'scan', 'cronograma', 'painel', 'resumo', 'recache'])
    def comandos_criticos_admin(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return

        if not verificar_sala(message, ID_ADMINS):
            bot.reply_to(message, "⚠️ Este comando de configuração só é aceito dentro da sala Mesa dos Admins.")
            return

        comando = message.text.split()[0].replace('/', '').strip().lower()

        if comando == 'update':
            bot.send_message(
                chat_id=message.chat.id, 
                text="Iniciando auto-diagnostico dos sistemas...",
                message_thread_id=message.message_thread_id
            )
            status_gemini = "OK"
            status_api_football = "OK"
            
            chave_gemini = os.getenv("GEMINI_API_KEY")
            chave_football = os.getenv("API_FOOTBALL_KEY")
            
            try:
                client = obter_cliente_gemini()
                client.models.generate_content(model='gemini-2.5-flash', contents="ping")
            except Exception as e:
                status_gemini = f"FALHA ({e})"
                
            try:
                primeira_chave = [k.strip() for k in chave_football.split(",") if k.strip()][0]
                headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': primeira_chave}
                res = requests.get("https://v3.football.api-sports.io/status", headers=headers, timeout=5)
                dados_status = res.json()
                
                if "response" not in dados_status or dados_status.get("errors"):
                    erro_recebido = dados_status.get("errors") if dados_status.get("errors") else dados_status
                    status_api_football = f"FALHA (Erro: {erro_recebido})"
                else:
                    status_api_football = "OK"
            except Exception as e:
                status_api_football = f"FALHA ({e})"
                
            relatorio_update = (
                "DIAGNOSTICO DE SISTEMA COMPLETO\n\n"
                f"Variavel GEMINI KEY: {'Configurada' if chave_gemini else 'AUSENTE'}\n"
                f"Variavel FOOTBALL KEY: {'Configurada' if chave_football else 'AUSENTE'}\n\n"
                f"Conexao Google Gemini IA: {status_gemini}\n"
                f"Conexao API-Football: {status_api_football}"
            )
            bot.send_message(
                chat_id=message.chat.id, 
                text=relatorio_update,
                message_thread_id=message.message_thread_id
            )

        elif comando == 'scan':
            bot.send_message(
                chat_id=message.chat.id, 
                text="🔄 Iniciando varredura manual de partidas para a próxima hora...",
                message_thread_id=message.message_thread_id
            )
            
            from analisador import verificar_e_enviar_pre_jogos
            qtd_enviados = verificar_e_enviar_pre_jogos(bot)
            
            if qtd_enviados > 0:
                bot.send_message(
                    chat_id=message.chat.id, 
                    text=f"✅ Varredura concluída! {qtd_enviados} novo(s) relatório(s) enviado(s) para a sala Pré-Jogo.",
                    message_thread_id=message.message_thread_id
                )
            else:
                bot.send_message(
                    chat_id=message.chat.id, 
                    text="ℹ️ Varredura concluída. Nenhuma nova partida agendada para a próxima hora nas ligas monitoradas.",
                    message_thread_id=message.message_thread_id
                )

        elif comando == 'cronograma':
            bot.send_message(
                chat_id=message.chat.id, 
                text="🔄 Buscando partidas de hoje e gerando tabela diária via IA...",
                message_thread_id=message.message_thread_id
            )
            
            headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': os.getenv("API_FOOTBALL_KEY")}
            from datetime import datetime, timezone, timedelta
            agora_brt = datetime.now(timezone.utc) - timedelta(hours=3)
            hoje_brt = agora_brt.strftime('%Y-%m-%d')
            
            try:
                res_cru = requests.get(f"https://v3.football.api-sports.io/fixtures?date={hoje_brt}", headers=headers, timeout=12)
                dados_crus = res_cru.json()
                total_mundo = len(dados_crus.get("response", []))
                erros_api = dados_crus.get("errors")
            except Exception as e:
                total_mundo, erros_api = 0, str(e)
            
            from analisador import obter_jogos_do_dia, gerar_cronograma_diario_ia, listar_ligas_monitoradas
            jogos = obter_jogos_do_dia()
            
            if jogos:
                texto_cronograma = gerar_cronograma_diario_ia(jogos)
                bot.send_message(
                    chat_id=int(os.getenv("TELEGRAM_CHAT_ID")),
                    text=texto_cronograma,
                    message_thread_id=ID_PRE_JOGO
                )
                bot.send_message(
                    chat_id=message.chat.id, 
                    text="✅ Cronograma diário gerado e enviado com sucesso para a sala Pré-Jogo!",
                    message_thread_id=message.message_thread_id
                )
            else:
                msg_diagnostico = (
                    "ℹ️ Nenhuma partida encontrada hoje nas suas ligas monitoradas.\n\n"
                    "🔍 PAINEL DE DIAGNÓSTICO DA API:\n"
                    f"• Data consultada: {hoje_brt}\n"
                    f"• Total de jogos no mundo hoje na API: {total_mundo}\n"
                    f"• Erros retornados pela API: {erros_api if erros_api else 'Nenhum'}\n"
                    f"• Ligas monitoradas ativas na memória: {listar_ligas_monitoradas()}"
                )
                bot.send_message(
                    chat_id=message.chat.id, 
                    text=msg_diagnostico,
                    message_thread_id=message.message_thread_id
                )

        elif comando == 'resumo':
            bot.send_message(
                chat_id=message.chat.id, 
                text="🔄 Coletando estatísticas detalhadas de escanteios, cartões e faltas dos jogos de hoje...",
                message_thread_id=message.message_thread_id
            )
            
            from analisador import obter_dados_recap_dia, gerar_resumo_diario_ia
            dados_recap = obter_dados_recap_dia()
            
            if dados_recap:
                bot.send_message(
                    chat_id=message.chat.id, 
                    text="🧠 Analisando resultados e auditando Greens/Reds com a IA do VAR do Lucro...",
                    message_thread_id=message.message_thread_id
                )
                
                texto_resumo = gerar_resumo_diario_ia(dados_recap)
                
                # SISTEMA DE SEGURANÇA CONTRA MENSAGENS LONGAS (FATIADOR DE CARACTERE)
                limite_telegram = 4000
                chat_canal_id = int(os.getenv("TELEGRAM_CHAT_ID"))
                
                if len(texto_resumo) <= limite_telegram:
                    # Envia normalmente caso caiba em 1 única mensagem
                    bot.send_message(
                        chat_id=chat_canal_id,
                        text=texto_resumo,
                        message_thread_id=ID_PRE_JOGO
                    )
                else:
                    # Fatia o texto em blocos de até 3900 caracteres para evitar ultrapassar o limite [1]
                    tamanho_fatia = 3900
                    partes = [texto_resumo[i:i+tamanho_fatia] for i in range(0, len(texto_resumo), tamanho_fatia)]
                    
                    for idx, parte in enumerate(partes):
                        bot.send_message(
                            chat_id=chat_canal_id,
                            text=f"📋 [Balanço Diário - Parte {idx+1}/{len(partes)}]\n\n{parte}",
                            message_thread_id=ID_PRE_JOGO
                        )
                        time.sleep(1) # Pausa de segurança de 1 segundo entre as fatias
                
                bot.send_message(
                    chat_id=message.chat.id, 
                    text="✅ Balanço diário consolidado e auditado postado com sucesso na sala Pré-Jogo!",
                    message_thread_id=message.message_thread_id
                )
            else:
                bot.send_message(
                    chat_id=message.chat.id, 
                    text="ℹ️ Nenhuma partida registrada hoje nas ligas monitoradas para gerar o fechamento.",
                    message_thread_id=message.message_thread_id
                )

        elif comando == 'recache':
            dono_id = int(os.getenv("DONO_TELEGRAM_ID", "0"))
            if message.from_user.id != dono_id:
                bot.reply_to(message, "⚠️ Comando restrito exclusivamente ao criador do bot.")
                return
                
            global ULTIMO_RECACHE_TIME
            tempo_decorrido = time.time() - ULTIMO_RECACHE_TIME
            cooldown_segundos = 900  # 15 minutos de proteção contra suspensão
            
            if tempo_decorrido < cooldown_segundos:
                minutos_restantes = round((cooldown_segundos - tempo_decorrido) / 60, 1)
                bot.reply_to(
                    message, 
                    f"⚠️ O comando /recache esta em cooldown de segurança para proteger a sua API contra suspensões.\n"
                    f"Tente novamente em {minutos_restantes} minutos."
                )
                return
                
            bot.send_message(
                chat_id=message.chat.id, 
                text="🔄 Forçando consulta na API-Football e reconstruindo o cache diário de jogos...",
                message_thread_id=message.message_thread_id
            )
            
            from analisador import forcar_atualizacao_cache
            resultado = forcar_atualizacao_cache()
            
            # Atualiza o cronômetro do cooldown apenas se a chamada deu certo
            if "sucesso" in resultado.lower():
                ULTIMO_RECACHE_TIME = time.time()
                
            bot.send_message(
                chat_id=message.chat.id, 
                text=resultado,
                message_thread_id=message.message_thread_id
            )

        elif comando == 'painel':
            nome_time = message.text.replace('/painel', '').strip()
            if not nome_time:
                bot.reply_to(message, "⚠️ Use o comando digitando o nome do time. Exemplo: /painel Flamengo")
                return
                
            bot.reply_to(message, f"🔍 Pesquisando dados e montando o painel de analise para '{nome_time}'...")
            
            from analisador import buscar_time_por_nome, traduzir_busca_para_ingles
            nome_time_en = traduzir_busca_para_ingles(nome_time)
            
            try:
                time_dados = buscar_time_por_nome(nome_time_en)
                
                if not time_dados:
                    bot.send_message(
                        chat_id=message.chat.id, 
                        text=f"❌ Nao encontrei nenhum time com o nome '{nome_time}'.",
                        message_thread_id=message.message_thread_id
                    )
                    return
                    
                time_id = time_dados["team"]["id"]
                time_nome = time_dados["team"]["name"]
                
                url_web_app = f"{os.getenv('WEBHOOK_URL')}/painel_time?team_id={time_id}&league_id=71&season=2024"
                
                teclado = telebot.types.InlineKeyboardMarkup()
                botao_panel = telebot.types.InlineKeyboardButton(
                    text=f"📊 Ver Estatísticas do {time_nome}",
                    web_app=telebot.types.WebAppInfo(url=url_web_app)
                )
                teclado.add(botao_panel)
                
                bot.send_message(
                    chat_id=message.chat.id,
                    text=f"💎 Painel estatístico pronto para o {time_nome}!",
                    reply_markup=teclado,
                    message_thread_id=message.message_thread_id
                )
            except Exception as e:
                bot.reply_to(message, f"Erro ao construir painel: {e}")

        elif comando == 'addliga':
            try:
                id_liga = int(message.text.split()[1])
                from analisador import adicionar_liga_monitorada
                if adicionar_liga_monitorada(id_liga):
                    bot.reply_to(message, f"Sucesso! A liga ID {id_liga} foi adicionada ao monitoramento.")
                else:
                    bot.reply_to(message, f"A liga ID {id_liga} ja estava no monitoramento.")
            except Exception:
                bot.reply_to(message, "⚠️ Use: /addliga <numero_id>")

        elif comando == 'remliga':
            try:
                id_liga = int(message.text.split()[1])
                from analisador import remover_liga_monitorada
                if remover_liga_monitorada(id_liga):
                    bot.reply_to(message, f"Sucesso! A liga ID {id_liga} foi removida.")
                else:
                    bot.reply_to(message, f"A liga ID {id_liga} nao foi encontrada.")
            except Exception:
                bot.reply_to(message, "⚠️ Use: /remliga <numero_id>")

        elif comando == 'verligas':
            from analisador import listar_ligas_monitoradas
            bot.send_message(
                chat_id=message.chat.id, 
                text=f"LIGAS ATIVAS NO MONITORAMENTO DO VAR:\n\nIDs Monitorados: {listar_ligas_monitoradas()}",
                message_thread_id=message.message_thread_id
            )

        elif comando == 'ids':
            try:
                arg_busca = message.text.replace('/ids', '').strip()
                if not arg_busca:
                    bot.reply_to(message, "Para buscar IDs de ligas use: /ids <nome_ou_pais>\nTabela completa: https://dashboard.api-sports.io/football/ids", disable_web_page_preview=True)
                else:
                    arg_busca_ingles = traduzir_busca_para_ingles(arg_busca)
                    from analisador import buscar_ids_ligas
                    res = buscar_ids_ligas(arg_busca_ingles)
                    if not res:
                        bot.send_message(
                            chat_id=message.chat.id, 
                            text="Nenhuma liga encontrada.",
                            message_thread_id=message.message_thread_id
                        )
                    else:
                        linhas = [f"• ID: {r['id']} | {r['nome']} ({r['pais']})" for r in res[:15]]
                        bot.send_message(
                            chat_id=message.chat.id, 
                            text="RESULTADO DA BUSCA DE LIGAS:\n\n" + "\n".join(linhas),
                            message_thread_id=message.message_thread_id
                        )
            except Exception as e:
                bot.reply_to(message, f"Erro ao buscar IDs: {e}")

    # =====================================================================
    # COMANDOS DE ADMINS - GRUPO 2: PERMITIDOS EM QUALQUER UMA DAS 4 SALAS
    # =====================================================================
    @bot.message_handler(commands=['bemvindo', 'bomdia', 'green', 'red', 'resenha'])
    def comandos_interacao_admin(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return

        thread_id = message.message_thread_id
        if thread_id is not None:
            thread_id = int(thread_id)
            if thread_id not in [ID_PRE_JOGO, ID_AO_VIVO, ID_RESENHA, ID_ADMINS]:
                bot.reply_to(message, "⚠️ Comandos administrativos nao sao permitidos nesta sala do forum.")
                return

        comando = message.text.split()[0].replace('/', '').strip().lower()

        if comando == 'bemvindo':
            prompt = (
                "Escreva uma mensagem de boas-vindas extremamente divertida, criativa e animada para um novo membro "
                "que acabou de entrar no nosso grupo do Telegram.\n"
                "TEMA DO GRUPO: 'VAR do Lucro' (grupo focado em análises técnicas de futebol e investimentos esportivos).\n"
                "A narrativa deve ser inspirada na cabine do VAR revisando os batimentos cardíacos, o perfil e a carteira do novato e 'confirmando no monitor' a aprovação para o lucro.\n"
                "REGRAS RÍGIDAS: NÃO use asteriscos (*) no texto final. Mantenha em português fluído do Brasil."
            )
            texto = gerar_texto_interativo_ia(prompt)
            bot.send_message(
                chat_id=message.chat.id, 
                text=texto,
                message_thread_id=message.message_thread_id
            )

        elif comando == 'bomdia':
            prompt = (
                "Escreva um bom dia extremamente enérgico, motivador e focado no sucesso para a nossa comunidade "
                "de investidores esportivos da 'VAR do Lucro'.\n"
                "Incentive-os a analisar bem, respeitar a gestão de stake (banca) e manter o controle emocional hoje.\n"
                "REGRAS RÍGIDAS: NÃO use asteriscos (*) no texto final. Mantenha em português."
            )
            texto = gerar_texto_interativo_ia(prompt)
            bot.send_message(
                chat_id=message.chat.id, 
                text=texto,
                message_thread_id=message.message_thread_id
            )

        elif comando == 'green':
            prompt = (
                "Escreva uma comemoração de GREEN (aposta ganha) extremamente explosiva, vitoriosa e barulhenta para a nossa comunidade 'VAR do Lucro'.\n"
                "Celebre a precisão técnica do nosso método VAR e comemore o lucro colocado no bolso hoje.\n"
                "REGRAS RÍGIDAS: NÃO use asteriscos (*) no texto final. Mantenha em português."
            )
            texto = gerar_texto_interativo_ia(prompt)
            bot.send_message(
                chat_id=message.chat.id, 
                text=texto,
                message_thread_id=message.message_thread_id
            )

        elif comando == 'red':
            prompt = (
                "Escreva uma mensagem de consolo técnica e psicológica pós-RED (aposta perdida) para a comunidade 'VAR do Lucro'.\n"
                "O tom deve ser profissional, calmo e altamente focado na importância de seguir a gestão de banca rigorosa (usar stake de 1% a 3%) "
                "e por que a matemática a longo prazo sempre vence as variações do futebol.\n"
                "REGRAS RÍGIDAS: NÃO use asteriscos (*) no texto final. Mantenha em português."
            )
            texto = gerar_texto_interativo_ia(prompt)
            bot.send_message(
                chat_id=message.chat.id, 
                text=texto,
                message_thread_id=message.message_thread_id
            )

        elif comando == 'resenha':
            prompt = (
                "Escreva uma curiosidade real, extremamente bizarra, boba ou engraçada sobre a história do futebol mundial.\n"
                "O texto deve ser curto, divertido e perfeito para prender a atenção do nosso grupo 'VAR do Lucro'.\n"
                "REGRAS RÍGIDAS: NÃO use asteriscos (*) no texto final. Mantenha em português."
            )
            texto = gerar_texto_interativo_ia(prompt)
            bot.send_message(
                chat_id=message.chat.id, 
                text=texto,
                message_thread_id=message.message_thread_id
            )

    # =====================================================================
    # MONITORAMENTO AUTOMÁTICO DE NOVOS MEMBROS (ENVIO NA SALA RESENHA)
    # =====================================================================
    @bot.message_handler(content_types=['new_chat_members'])
    def boas_vindas_automatico(message):
        if not ID_RESENHA:
            return

        prompt = (
            "Escreva uma mensagem de boas-vindas extremamente divertida, criativa e animada para um novo membro "
            "que acabou de entrar no nosso grupo do Telegram.\n"
            "TEMA DO GRUPO: 'VAR do Lucro' (grupo focado em análises técnicas de futebol e investimentos esportivos).\n"
            "A narrativa deve ser inspirada na cabine do VAR revisando os batimentos cardíacos, o perfil e a carteira do novato e 'confirmando no monitor' a aprovação para o lucro.\n"
            "REGRAS RÍGIDAS: NÃO use asteriscos (*) no texto final. Mantenha em português fluído do Brasil."
        )
        texto = gerar_texto_interativo_ia(prompt)

        try:
            bot.send_message(
                chat_id=message.chat.id,
                text=texto,
                message_thread_id=ID_RESENHA
            )
        except Exception as e:
            print(f"Erro ao processar as boas-vindas automatizadas: {e}")