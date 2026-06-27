import os
import telebot
from telebot import TeleBot
import requests
from analisador import buscar_jogo_ao_vivo_por_time, analisar_ao_vivo_e_formatar, obter_jogos_do_dia, gerar_relatorio_pre_jogo, obter_cliente_gemini

def eh_admin(bot: TeleBot, message) -> bool:
    """
    Verifica se o usuário que enviou o comando é administrador ou criador do grupo.
    Se for um chat privado (direto com o bot), a permissão é concedida automaticamente.
    """
    if message.chat.type == "private":
        return True
    try:
        status_membro = bot.get_chat_member(message.chat.id, message.from_user.id).status
        return status_membro in ["administrator", "creator"]
    except Exception as e:
        print(f"Erro ao verificar permissões de admin: {e}")
        return False

def registrar_comandos(bot: TeleBot):
    """
    Registra todos os manipuladores de comandos (Handlers) do bot do Telegram.
    """

    # ==========================================
    # COMANDOS PÚBLICOS (QUALQUER UM PODE USAR)
    # ==========================================

    @bot.message_handler(commands=['start', 'ajuda'])
    def enviar_ajuda(message):
        texto = (
            "💎 Central de Inteligência Esportiva 💎\n\n"
            "Comandos para usuários:\n"
            "👉 /aovivo <nome do time>: Busca estatísticas de um jogo acontecendo agora.\n"
            "👉 /prejogo <nome do time>: Gera o relatório de análise pré-jogo.\n\n"
            "Os demais comandos de animação e controle são exclusivos para administradores do grupo."
        )
        bot.reply_to(message, texto)

    @bot.message_handler(commands=['aovivo'])
    def comando_ao_vivo(message):
        args = message.text.replace('/aovivo', '').strip()
        if not args:
            bot.reply_to(message, "⚠️ Digite o nome do time. Exemplo: /aovivo Real Madrid")
            return
        
        bot.reply_to(message, f"🔍 Procurando partida ao vivo para '{args}'...")
        dados_jogo = buscar_jogo_ao_vivo_por_time(args)
        
        if not dados_jogo:
            bot.send_message(message.chat.id, f"❌ Nenhuma partida ao vivo encontrada para '{args}' no momento.")
            return
            
        bot.send_message(message.chat.id, "📊 Partida encontrada! Calculando probabilidades e notícias...")
        analise_final = analisar_ao_vivo_e_formatar(dados_jogo)
        bot.send_message(message.chat.id, analise_final)

    @bot.message_handler(commands=['prejogo'])
    def comando_pre_jogo(message):
        args = message.text.replace('/prejogo', '').strip()
        if not args:
            bot.reply_to(message, "⚠️ Digite o nome do time. Exemplo: /prejogo Flamengo")
            return
            
        bot.reply_to(message, f"🔍 Buscando cronograma de hoje para '{args}'...")
        jogos_hoje = obter_jogos_do_dia()
        jogo_encontrado = None
        args_min = args.lower().strip()
        
        for jogo in jogos_hoje:
            casa = jogo["teams"]["home"]["name"].lower()
            fora = jogo["teams"]["away"]["name"].lower()
            if args_min in casa or args_min in fora:
                jogo_encontrado = jogo
                break
                
        if not juego_encontrado:
            bot.send_message(message.chat.id, f"❌ Não encontrei nenhuma partida para hoje com o nome '{args}'.")
            return
            
        bot.send_message(message.chat.id, "🧠 Gerando Relatório de Inteligência VAR do Lucro...")
        relatorio = gerar_relatorio_pre_jogo(jogo_encontrado)
        bot.send_message(message.chat.id, relatorio)


    # ==========================================
    # COMANDOS DE ADMINISTRADORES (BLOQUEADOS)
    # ==========================================

    @bot.message_handler(commands=['addliga'])
    def comando_add_liga(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return
        
        try:
            # Extrai o ID digitado pelo admin
            id_liga = int(message.text.replace('/addliga', '').strip())
            from analisador import adicionar_liga_monitorada
            
            sucesso = adicionar_liga_monitorada(id_liga)
            if sucesso:
                bot.reply_to(message, f"Sucesso! A liga ID {id_liga} foi adicionada ao monitoramento ativo.")
            else:
                bot.reply_to(message, f"A liga ID {id_liga} ja estava na lista de monitoramento.")
        except ValueError:
            bot.reply_to(message, "⚠️ ID invalido. Use o comando enviando apenas numeros. Exemplo: /addliga 71")

    @bot.message_handler(commands=['remliga'])
    def comando_rem_liga(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return
        
        try:
            id_liga = int(message.text.replace('/remliga', '').strip())
            from analisador import remover_liga_monitorada
            
            sucesso = remover_liga_monitorada(id_liga)
            if sucesso:
                bot.reply_to(message, f"Sucesso! A liga ID {id_liga} foi removida do monitoramento.")
            else:
                bot.reply_to(message, f"A liga ID {id_liga} nao foi encontrada na lista.")
        except ValueError:
            bot.reply_to(message, "⚠️ ID invalido. Use o comando enviando apenas numeros. Exemplo: /remliga 71")

    @bot.message_handler(commands=['verligas'])
    def comando_ver_ligas(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return
            
        from analisador import listar_ligas_monitoradas
        ligas = listar_ligas_monitoradas()
        
        texto = (
            "LIGAS ATIVAS NO MONITORAMENTO DO VAR:\n\n"
            f"IDs Monitorados: {ligas}\n\n"
            "Dica de IDs comuns:\n"
            "• 71: Brasileirao Serie A\n"
            "• 39: Premier League (Inglaterra)\n"
            "• 140: La Liga (Espanha)\n"
            "• 2: Champions League (Europa)"
        )
        bot.send_message(message.chat.id, texto)
    
    @bot.message_handler(commands=['bemvindo'])
    def comando_bemvindo(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return
        
        texto = (
            "Atencao cabine do VAR! Temos um novo integrante na mesa de operacoes!\n\n"
            "Analisando o perfil do novato em nossa tela de transmissao...\n"
            "Checando dados... Verificando batimentos cardiacos... Analisando a carteira...\n\n"
            "DECISAO CONFIRMADA NO MONITOR:\n"
            "Cadastro aprovado com sucesso! Seja muito bem-vindo ao VAR do Lucro!\n"
            "Prepare sua planilha, ajuste sua stake e junte-se aos operadores profissionais de elite."
        )
        bot.send_message(message.chat.id, texto)

    @bot.message_handler(commands=['bomdia'])
    def comando_bomdia(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return
        
        texto = (
            "Bom dia, mercado! Os monitores ja estao ligados e as APIs aquecidas!\n\n"
            "Hoje o dia promete muitas oportunidades na nossa mesa de analise. "
            "Lembre-se das regras de ouro para hoje:\n"
            "1. Proteja seu capital (stake controlada).\n"
            "2. Estude os relatorios antes de clicar.\n"
            "3. Mantenha a calma de um monge, ganhando ou perdendo.\n\n"
            "Que o valor esperado positivo esteja conosco. Bons investimentos a todos!"
        )
        bot.send_message(message.chat.id, texto)

    @bot.message_handler(commands=['green'])
    def comando_green(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return
        
        texto = (
            "EXPLODIU O GREEN DA NOSSA ANALISE!\n\n"
            "A analise cirurgica do nosso relatorio bateu exatamente com o andamento do jogo!\n"
            "Quem seguiu a gestao de banca e entrou na recomendacao do VAR do Lucro acabou de colocar dinheiro no bolso!\n"
            "O mercado tentou segurar, mas a nossa leitura tecnica foi implacavel.\n"
            "Parabens aos lucros coletados! Comemore sem perder o foco na proxima operacao."
        )
        bot.send_message(message.chat.id, texto)

    @bot.message_handler(commands=['red'])
    def comando_red(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return
        
        texto = (
            "Atenção operadores: Red detectado.\n\n"
            "O futebol tem variaveis imprevisiveis que nenhuma estatistica consegue blindar 100 por cento.\n"
            "Mas e aqui que se separam os amadores dos profissionais:\n"
            "Seguir estritamente a nossa stake de 1 a 3 por cento garante que esse tropeço nao afete sua saude financeira.\n"
            "Nao tente recuperar o valor perdido imediatamente com apostas desesperadas sem estudo.\n"
            "Mantenha o controle emocional. A longo prazo, a consistencia matematica sempre vence."
        )
        bot.send_message(message.chat.id, texto)

    @bot.message_handler(commands=['resenha'])
    def comando_resenha(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return
        
        # Curiosidade bizarra de futebol selecionada de forma aleatória e direta
        import random
        curiosidades = [
            "Voce sabia que em 1998, um raio atingiu o gramado durante um jogo no Congo e matou todos os 11 jogadores de um time, enquanto o outro time saiu completamente ileso? Bizarro demais!",
            "Na Inglaterra, o jogador Lee Todd levou o cartao vermelho mais rapido da historia: apenas 2 segundos de jogo! Ao ouvir o apito inicial do juiz perto do seu ouvido, ele exclamou: Caramba, isso foi muito alto! E foi expulso.",
            "Em 1945, um jogo entre Arsenal e Dynamo de Moscou ocorreu sob uma névoa tao densa que ninguem enxergava nada. O Dynamo fez substituicoes sem ninguem perceber e acabou jogando com 15 jogadores em campo por quase meia hora!"
        ]
        
        texto = "CURIOSIDADE DO VAR DO LUCRO\n\n" + random.choice(curiosidades)
        bot.send_message(message.chat.id, texto)

    @bot.message_handler(commands=['update'])
    def comando_update(message):
        if not eh_admin(bot, message):
            bot.reply_to(message, "⚠️ Apenas administradores podem usar este comando.")
            return
        
        bot.reply_to(message, "Iniciando auto-diagnostico dos sistemas...")
        
        status_gemini = "OK"
        status_api_football = "OK"
        
        # Teste 1: Chaves de ambiente
        chave_gemini = os.getenv("GEMINI_API_KEY")
        chave_football = os.getenv("API_FOOTBALL_KEY")
        
        # Teste 2: Conexao Gemini
        try:
            client = obter_cliente_gemini()
            # Uma chamada levissima de teste
            client.models.generate_content(
                model='gemini-2.5-flash',
                contents="ping",
            )
        except Exception as e:
            status_gemini = f"FALHA ({e})"
            
        # Teste 3: Conexao API Football
        try:
            headers = {'x-rapidapi-host': 'v3.football.api-sports.io', 'x-rapidapi-key': chave_football}
            res = requests.get("https://v3.football.api-sports.io/status", headers=headers, timeout=5)
            if res.status_code != 200:
                status_api_football = f"FALHA (Status HTTP {res.status_code})"
        except Exception as e:
            status_api_football = f"FALHA ({e})"
            
        relatorio_update = (
            "DIAGNOSTICO DE SISTEMA COMPLETO\n\n"
            f"Variavel GEMINI KEY:
