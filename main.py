import os
import time
import threading
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template_string, request, jsonify
import analisador
import comandos

app = Flask(__name__)

# Controle de envio de alertas para evitar duplicações
ALERTAS_ENVIADOS = {}

# Controle de envio do Bom Dia
BOM_DIA_ENVIADO = None

# ==========================================
# PAINEL WEB APP (ESTILO IDÊNTICO À FOTO 2)
# ==========================================

HTML_PAINEL = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VAR do Lucro - Painel Tático</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .custom-scroll::-webkit-scrollbar {
            height: 4px;
        }
        .custom-scroll::-webkit-scrollbar-thumb {
            background-color: #14b8a6;
            border-radius: 10px;
        }
    </style>
</head>
<body class="bg-[#121824] text-slate-100 font-sans min-h-screen">
    <div class="max-w-md mx-auto space-y-4 pb-12">
        
        <!-- Header da Página -->
        <div class="bg-[#1a2333] px-4 py-3 text-center border-b border-slate-700">
            <h1 class="text-xs font-bold tracking-widest text-[#00f5d4]">SEE HOW IT LOOKS</h1>
        </div>

        <!-- Menu Superior de Categorias Rolável (Foto 2) -->
        <div class="bg-[#1a2333] px-4 py-2 border-b border-slate-700">
            <div class="flex space-x-6 overflow-x-auto custom-scroll pb-1 text-xs font-semibold text-slate-400 whitespace-nowrap">
                <span>Volleyball</span>
                <span>AFL</span>
                <span class="text-teal-400 border-b-2 border-teal-400 pb-1">Football</span>
                <span>Formula-1</span>
                <span>MMA</span>
                <span>NBA</span>
                <span>NFL</span>
            </div>
        </div>

        <!-- Bloco de Perfil do Time -->
        <div class="px-4 space-y-1">
            <div class="flex items-center space-x-2">
                <h2 class="text-lg font-bold text-white">{{ dados.nome }}</h2>
                <i class="far fa-star text-slate-400 cursor-pointer"></i>
            </div>
            <div class="text-xs text-slate-400 space-y-0.5">
                <p>Founded: {{ dados.stats.ano_fundacao }}</p>
                <p>Country: {{ dados.stats.pais }}</p>
            </div>
        </div>

        <!-- Abas de Navegação (Foto 2) -->
        <div class="bg-[#1a2333] border-y border-slate-700">
            <div class="grid grid-cols-3 text-center text-xs font-bold">
                <span class="py-3 bg-[#1e293b] text-teal-400 border-b-2 border-teal-400 uppercase tracking-wider">Statistics</span>
                <span class="py-3 text-slate-400 uppercase tracking-wider">Squads</span>
                <span class="py-3 text-slate-400 uppercase tracking-wider">Standings</span>
            </div>
        </div>

        <!-- Competição -->
        <div class="px-4 py-2 bg-[#1e293b]/50 mx-4 rounded-lg text-xs font-semibold text-slate-300">
            🏆 Major League Soccer (2026)
        </div>

        <!-- Anéis de Estatísticas (Foto 2 Visual Circles) -->
        <div class="grid grid-cols-3 gap-2 px-4">
            <div class="bg-[#1a2333] p-3 rounded-xl border border-slate-800 text-center space-y-2">
                <div class="relative w-16 h-16 mx-auto flex items-center justify-center">
                    <span class="text-xs font-bold">44%<br><span class="text-[9px] text-slate-400">WINS</span></span>
                    <svg class="absolute inset-0 w-full h-full -rotate-90">
                        <circle cx="32" cy="32" r="28" stroke="#334155" stroke-width="4" fill="transparent" />
                        <circle cx="32" cy="32" r="28" stroke="#14b8a6" stroke-width="4" fill="transparent" stroke-dasharray="175" stroke-dashoffset="98" />
                    </svg>
                </div>
                <p class="text-[10px] text-slate-400 font-semibold">Played: 29</p>
            </div>

            <div class="bg-[#1a2333] p-3 rounded-xl border border-slate-800 text-center space-y-2">
                <div class="relative w-16 h-16 mx-auto flex items-center justify-center">
                    <span class="text-[9px] font-bold text-slate-200">58.6%<br><span class="text-[7px] text-slate-400">{{ dados.stats.lineup_preferida }}</span></span>
                    <svg class="absolute inset-0 w-full h-full -rotate-90">
                        <circle cx="32" cy="32" r="28" stroke="#334155" stroke-width="4" fill="transparent" />
                        <circle cx="32" cy="32" r="28" stroke="#eab308" stroke-width="4" fill="transparent" stroke-dasharray="175" stroke-dashoffset="72" />
                    </svg>
                </div>
                <p class="text-[10px] text-slate-400 font-semibold">Lineups</p>
            </div>

            <div class="bg-[#1a2333] p-3 rounded-xl border border-slate-800 text-center space-y-2">
                <div class="relative w-16 h-16 mx-auto flex items-center justify-center">
                    <span class="text-[9px] font-bold text-slate-200">100%<br><span class="text-[8px] text-slate-400">SCOR</span></span>
                    <svg class="absolute inset-0 w-full h-full -rotate-90">
                        <circle cx="32" cy="32" r="28" stroke="#334155" stroke-width="4" fill="transparent" />
                        <circle cx="32" cy="32" r="28" stroke="#22c55e" stroke-width="4" fill="transparent" stroke-dasharray="175" stroke-dashoffset="0" />
                    </svg>
                </div>
                <p class="text-[10px] text-slate-400 font-semibold">Penalties</p>
            </div>
        </div>

        <!-- Indicador de Direção Home/Away -->
        <div class="flex justify-between px-6 text-xs font-bold text-slate-400">
            <span class="text-teal-400">HOME</span>
            <span class="text-amber-400">AWAY</span>
        </div>

        <!-- Barras Horizontais Bicolorizadas de Estatísticas (Foto 2) -->
        <div class="bg-[#1a2333] p-4 mx-4 rounded-xl space-y-3 border border-slate-800 text-xs">
            
            <!-- Wins -->
            <div class="space-y-1">
                <div class="flex justify-between font-semibold">
                    <span class="text-slate-300">Wins : {{ dados.stats.vitorias }}</span>
                </div>
                <div class="w-full h-2.5 bg-slate-700 rounded-full flex overflow-hidden">
                    <div class="bg-teal-500 h-full" style="width: 60%"></div>
                    <div class="bg-amber-500 h-full" style="width: 40%"></div>
                </div>
            </div>

            <!-- Losses -->
            <div class="space-y-1">
                <div class="flex justify-between font-semibold">
                    <span class="text-slate-300">Losses : {{ dados.stats.derrotas }}</span>
                </div>
                <div class="w-full h-2.5 bg-slate-700 rounded-full flex overflow-hidden">
                    <div class="bg-teal-500 h-full" style="width: 45%"></div>
                    <div class="bg-amber-500 h-full" style="width: 55%"></div>
                </div>
            </div>

            <!-- Draws -->
            <div class="space-y-1">
                <div class="flex justify-between font-semibold">
                    <span class="text-slate-300">Draws : {{ dados.stats.empates }}</span>
                </div>
                <div class="w-full h-2.5 bg-slate-700 rounded-full flex overflow-hidden">
                    <div class="bg-teal-500 h-full" style="width: 50%"></div>
                    <div class="bg-amber-500 h-full" style="width: 50%"></div>
                </div>
            </div>

            <!-- Clean sheets -->
            <div class="space-y-1">
                <div class="flex justify-between font-semibold">
                    <span class="text-slate-300">Clean sheets : {{ dados.stats.clean_sheets }}</span>
                </div>
                <div class="w-full h-2.5 bg-slate-700 rounded-full flex overflow-hidden">
                    <div class="bg-teal-500 h-full" style="width: 70%"></div>
                    <div class="bg-amber-500 h-full" style="width: 30%"></div>
                </div>
            </div>

            <!-- Failed to score -->
            <div class="space-y-1">
                <div class="flex justify-between font-semibold">
                    <span class="text-slate-300">Failed to score : {{ dados.stats.failed_to_score }}</span>
                </div>
                <div class="w-full h-2.5 bg-slate-700 rounded-full flex overflow-hidden">
                    <div class="bg-teal-500 h-full" style="width: 40%"></div>
                    <div class="bg-amber-500 h-full" style="width: 60%"></div>
                </div>
            </div>

        </div>

        <!-- Cards Disciplinar (Gráfico de Colunas na Parte Inferior) -->
        <div class="bg-[#1a2333] p-4 mx-4 rounded-xl border border-slate-800 space-y-4">
            <h3 class="text-xs font-bold tracking-wider text-slate-400 uppercase">Cards (Season Distribution)</h3>
            <div class="flex items-end justify-between h-20 px-2 pt-2 border-b border-slate-700">
                <div class="w-8 bg-amber-500 rounded-t-sm h-[20%]"></div>
                <div class="w-8 bg-amber-500 rounded-t-sm h-[40%]"></div>
                <div class="w-8 bg-amber-500 rounded-t-sm h-[60%]"></div>
                <div class="w-8 bg-amber-500 rounded-t-sm h-[80%] border-t-4 border-rose-500"></div>
                <div class="w-8 bg-amber-500 rounded-t-sm h-[50%]"></div>
                <div class="w-8 bg-amber-500 rounded-t-sm h-[95%] border-t-4 border-rose-500"></div>
                <div class="w-8 bg-amber-500 rounded-t-sm h-[35%] border-t-2 border-rose-500"></div>
            </div>
        </div>

    </div>
</body>
</html>
"""

@app.route("/")
def home():
    return "VAR do Lucro Bot ativo na nuvem com cache e controle de rotas integrados."

@app.route("/painel")
def painel():
    time_solicitado = request.args.get("time", "")
    if not time_solicitado:
        return "Nenhum time foi especificado.", 400

    dados_painel = analisador.consultar_dados_painel(time_solicitado)
    if not dados_painel:
        return f"Não foi possível encontrar dados da equipe: {time_solicitado}", 404

    return render_template_string(HTML_PAINEL, dados=dados_painel)

# ==========================================
# THREAD 1: TAREFAS AGENDADAS E ALERTA CONTADORES
# ==========================================

def loop_tarefas_agendadas():
    global BOM_DIA_ENVIADO
    print("[THREAD AGENDADOR] Rodando em segundo plano.")
    
    while True:
        try:
            hoje_br = analisador.obter_data_brasilia()
            hora_str = hoje_br.strftime("%H:%M")
            data_str = hoje_br.strftime("%Y-%m-%d")

            # 1. Publicação automática do Cronograma Diário à meia-noite (00:00)
            if hora_str == "00:00":
                print("[AGENDADOR] Meia-noite BRT. Atualizando cronograma diário...")
                comandos.enviar_cronograma_diario()
                time.sleep(70) 
                continue

            # 2. Bom dia automático às 06:00 AM (Roteado para a Resenha)
            if hora_str == "06:00" and BOM_DIA_ENVIADO != data_str:
                print("[AGENDADOR] 06h00 AM BRT. Enviando mensagem de bom dia...")
                prompt = "Crie uma mensagem divertida de bom dia para o grupo de apostadores e analistas, incentivando a lucrar hoje."
                resposta = analisador.perguntar_ao_gemini(prompt)
                
                comandos.bot.send_message(
                    comandos.CHAT_ID_GERAL,
                    resposta,
                    message_thread_id=int(comandos.TOPICO_RESENHA) if comandos.TOPICO_RESENHA else None,
                    parse_mode="HTML"
                )
                BOM_DIA_ENVIADO = data_str
                time.sleep(70)
                continue

            # 3. Processamento de Contagens Regressivas (Alertas 3h e 2h AGRUPADOS)
            jogos = analisador.obter_jogos_do_dia()
            chat_id = comandos.CHAT_ID_GERAL
            topico_pre = int(comandos.TOPICO_PRE_JOGO) if comandos.TOPICO_PRE_JOGO else None

            if jogos and chat_id:
                jogos_3h_pendentes = []
                jogos_2h_pendentes = []

                for j in jogos:
                    match_id = str(j["id"])
                    
                    try:
                        dt_utc = datetime.fromisoformat(j["data_utc"].replace("Z", "+00:00"))
                        dt_br = dt_utc.astimezone(timezone(timedelta(hours=-3)))
                    except Exception:
                        continue

                    tempo_restante = dt_br - hoje_br
                    minutos_restantes = tempo_restante.total_seconds() / 60

                    if match_id not in ALERTAS_ENVIADOS:
                        ALERTAS_ENVIADOS[match_id] = {"3h": False, "2h": False, "1h": False, "10m": False}

                    # Coleta partidas que estão na janela de 3h
                    if 170 <= minutos_restantes <= 180 and not ALERTAS_ENVIADOS[match_id]["3h"]:
                        jogos_3h_pendentes.append(j)

                    # Coleta partidas que estão na janela de 2h
                    elif 110 <= minutos_restantes <= 120 and not ALERTAS_ENVIADOS[match_id]["2h"]:
                        jogos_2h_pendentes.append(j)

                    # 4. Alerta de 1 Hora - MODELAGEM DINÂMICA (Gera a análise 1 hora antes com dados de escalação frescos)
                    elif 50 <= minutos_restantes <= 60 and not ALERTAS_ENVIADOS[match_id]["1h"]:
                        print(f"[AGENDADOR] Gerando Dossiê Técnico atualizado para {j['mandante']} x {j['visitante']}...")
                        
                        # Roda os cálculos com os indicadores estruturados de pré-jogo
                        arbitro_stats_padrao = {
                            "media_cartoes": 5.2,
                            "media_faltas": 26.0,
                            "rigor_cartao_por_falta": 0.20
                        }
                        dados_iniciais_jogo = {
                            "tempo": 0.1,
                            "esc_m": 0, "esc_v": 0,
                            "atqp_m": 0, "atqp_v": 0
                        }
                        
                        proj = analisador.calcular_projecoes_secundarias(dados_iniciais_jogo, arbitro_stats_padrao)

                        prompt = (
                            f"Crie um Dossiê Técnico Completo de Inteligência para a partida {j['mandante']} x {j['visitante']} pela liga {j['liga']}.\n"
                            "Gere o dossiê contendo:\n"
                            "1. Uma simulação da precificação de probabilidade e odd justa para vitória, empate e gols.\n"
                            "2. Projeções para os mercados secundários baseadas nestes indicadores matemáticos de nosso algoritmo:\n"
                            f"   - Escanteios Projetados: {proj['escanteios_final_projetado']}\n"
                            f"   - Cartões Projetados: {proj['cartoes_final_projetado']}\n"
                            f"   - Faltas Projetadas: {proj['faltas_final_projetado']}\n"
                            "3. Uma recomendação de aposta com valor esperado positivo (+EV) fundamentada e aplicando o Critério de Kelly Fracionário para sugerir a stake segura.\n"
                            "Diretriz Crítica: Nunca utilize o caractere asterisco (*) em sua resposta."
                        )
                        
                        texto_dossie = analisador.perguntar_ao_gemini(prompt)

                        comandos.bot.send_message(
                            chat_id, 
                            f"📊 <b>DOSSIÊ TÉCNICO (+EV)</b>\n\n{texto_dossie}", 
                            message_thread_id=topico_pre, 
                            parse_mode="HTML"
                        )
                        ALERTAS_ENVIADOS[match_id]["1h"] = True

                # Dispara mensagem agrupada para os jogos de 3 horas
                if jogos_3h_pendentes:
                    nomes_jogos = " e ".join([f"{jg['mandante']} x {jg['visitante']}" for jg in jogos_3h_pendentes])
                    prompt = f"Gere uma chamada divertida dizendo que restam apenas 3 horas para o início dos confrontos: {nomes_jogos}."
                    texto_ia = analisador.perguntar_ao_gemini(prompt)
                    
                    comandos.bot.send_message(
                        chat_id,
                        f"🔥 <b>VAR REGRESSIVO - 3 HORAS</b>\n\n{texto_ia}",
                        message_thread_id=topico_pre,
                        parse_mode="HTML"
                    )
                    for jg in jogos_3h_pendentes:
                        ALERTAS_ENVIADOS[str(jg["id"])]["3h"] = True

                # Dispara mensagem agrupada para os jogos de 2 horas
                if jogos_2h_pendentes:
                    nomes_jogos = " e ".join([f"{jg['mandante']} x {jg['visitante']}" for jg in jogos_2h_pendentes])
                    prompt = f"Gere uma chamada divertida dizendo que restam apenas 2 horas para o início dos confrontos: {nomes_jogos}."
                    texto_ia = analisador.perguntar_ao_gemini(prompt)
                    
                    comandos.bot.send_message(
                        chat_id,
                        f"⚠️ <b>VAR REGRESSIVO - 2 HORAS</b>\n\n{texto_ia}",
                        message_thread_id=topico_pre,
                        parse_mode="HTML"
                    )
                    for jg in jogos_2h_pendentes:
                        ALERTAS_ENVIADOS[str(jg["id"])]["2h"] = True

        except Exception as e:
            print(f"[ERRO AGENDADOR] Falha no processamento interno do loop: {str(e)}")

        time.sleep(60)

# ==========================================
# THREAD 2: CONTROLE DE EXECUÇÃO
# ==========================================

def iniciar_bot_polling():
    print("[THREAD POLLING] Bot de mensagens rodando.")
    while True:
        try:
            comandos.bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"[ERRO POLLING] Falha na conexão com o Telegram: {str(e)}")
            time.sleep(10)

if __name__ == "__main__":
    # Preenche o cronograma diário inicial em cache ao iniciar o aplicativo
    try:
        analisador.obter_jogos_do_dia(forcar=True)
    except Exception as e:
        print(f"[ERRO INICIAL] Falha ao carregar cache de jogos: {str(e)}")

    t_bot = threading.Thread(target=iniciar_bot_polling, daemon=True)
    t_bot.start()

    t_agendador = threading.Thread(target=loop_tarefas_agendadas, daemon=True)
    t_agendador.start()

    porta = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=porta)