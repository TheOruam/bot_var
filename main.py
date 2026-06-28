import os
import time
import threading
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template_string, request, jsonify
import analisador
import comandos

app = Flask(__name__)

# Memória persistente de controle dos alertas disparados para não enviar duplicado
ALERTAS_ENVIADOS = {}

# ==========================================
# PAINEL WEB APP (TEMPLATES HTML/CSS/JS)
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
</head>
<body class="bg-slate-900 text-white font-sans min-h-screen">
    <div class="max-w-md mx-auto p-4 space-y-6 pb-12">
        
        <!-- Header -->
        <div class="flex items-center space-x-4 bg-slate-800 p-4 rounded-xl shadow-lg border border-emerald-500/30">
            <img src="{{ dados.escudo }}" alt="Escudo" class="w-16 h-16 object-contain rounded-full bg-slate-700 p-1">
            <div>
                <h1 class="text-xl font-bold text-emerald-400">{{ dados.nome }}</h1>
                <p class="text-sm text-slate-400">Desempenho da Equipe</p>
            </div>
        </div>

        <!-- Estatísticas Básicas (Gráficos) -->
        <div class="bg-slate-800 p-5 rounded-xl shadow-lg space-y-4">
            <h2 class="text-md font-semibold text-slate-300">Desempenho Geral</h2>
            <div class="relative h-48 w-full">
                <canvas id="graficoPartidas"></canvas>
            </div>
            
            <div class="grid grid-cols-3 gap-2 text-center pt-2">
                <div class="bg-slate-700/50 p-2 rounded-lg">
                    <span class="block text-xs text-slate-400">Vitórias</span>
                    <span class="text-lg font-bold text-emerald-400">{{ dados.stats.vitorias }}</span>
                </div>
                <div class="bg-slate-700/50 p-2 rounded-lg">
                    <span class="block text-xs text-slate-400">Empates</span>
                    <span class="text-lg font-bold text-slate-300">{{ dados.stats.empates }}</span>
                </div>
                <div class="bg-slate-700/50 p-2 rounded-lg">
                    <span class="block text-xs text-slate-400">Derrotas</span>
                    <span class="text-lg font-bold text-rose-500">{{ dados.stats.derrotas }}</span>
                </div>
            </div>
        </div>

        <!-- Detalhes de Gols -->
        <div class="bg-slate-800 p-5 rounded-xl shadow-lg grid grid-cols-2 gap-4">
            <div>
                <span class="text-xs text-slate-400">Gols Marcados</span>
                <p class="text-2xl font-bold text-emerald-400">{{ dados.stats.gols_marcados }}</p>
            </div>
            <div>
                <span class="text-xs text-slate-400">Gols Sofridos</span>
                <p class="text-2xl font-bold text-rose-500">{{ dados.stats.gols_sofridos }}</p>
            </div>
        </div>

        <!-- Elenco (Squad) -->
        <div class="bg-slate-800 p-5 rounded-xl shadow-lg space-y-4">
            <h2 class="text-md font-semibold text-slate-300">Elenco Cadastrado</h2>
            <div class="max-h-60 overflow-y-auto space-y-2 pr-1">
                {% if dados.jogadores %}
                    {% for j in dados.jogadores %}
                    <div class="flex justify-between items-center bg-slate-700/30 p-2.5 rounded-lg border-l-4 border-emerald-500">
                        <div>
                            <p class="font-medium text-sm">{{ j.nome }}</p>
                            <span class="text-[11px] text-slate-400">{{ j.posicao }}</span>
                        </div>
                        <span class="text-xs font-semibold bg-slate-700 px-2 py-0.5 rounded text-emerald-300">{{ j.idade }} anos</span>
                    </div>
                    {% endfor %}
                {% else %}
                    <p class="text-sm text-slate-400">Informações de elenco não localizadas para esta liga.</p>
                {% endif %}
            </div>
        </div>
        
    </div>

    <script>
        const ctx = document.getElementById('graficoPartidas').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Vitórias', 'Empates', 'Derrotas'],
                datasets: [{
                    data: [{{ dados.stats.vitorias }}, {{ dados.stats.empates }}, {{ dados.stats.derrotas }}],
                    backgroundColor: ['#10b981', '#64748b', '#f43f5e'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                cutout: '75%'
            }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return "VAR do Lucro Bot rodando ativamente com status estável na porta do Render."

@app.route("/painel")
def painel():
    time_solicitado = request.args.get("time", "")
    if not time_solicitado:
        return "Nenhum time foi especificado para exibição do painel.", 400

    dados_painel = analisador.consultar_dados_painel(time_solicitado)
    if not dados_painel:
        return f"Dados não encontrados para a equipe: {time_solicitado}", 404

    return render_template_string(HTML_PAINEL, dados=dados_painel)

# ==========================================
# THREAD 1: TAREFAS AGENDADAS E ALERTA CONTADORES
# ==========================================

def loop_tarefas_agendadas():
    """Gerencia alertas de contagem regressiva e publicação automática do cronograma."""
    print("[THREAD AGENDADOR] Iniciado com sucesso.")
    
    while True:
        try:
            hoje_br = analisador.obter_data_brasilia()
            hora_str = hoje_br.strftime("%H:%M")
            data_str = hoje_br.strftime("%Y-%m-%d")

            # 1. Publicação automática do Cronograma Diário à meia-noite
            if hora_str == "00:00":
                print("[AGENDADOR] Meia-noite detectada. Atualizando dados e gerando novo cronograma...")
                comandos.enviar_cronograma_diario()
                time.sleep(70) 
                continue

            # 2. Verificação das contagens regressivas para os jogos cadastrados no cache
            jogos = analisador.obter_jogos_do_dia()
            chat_id = comandos.CHAT_ID_GERAL
            topico_pre = int(comandos.TOPICO_PRE_JOGO) if comandos.TOPICO_PRE_JOGO else None

            if jogos and chat_id:
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

                    # Alerta de 3 Horas
                    if 170 <= minutos_restantes <= 180 and not ALERTAS_ENVIADOS[match_id]["3h"]:
                        prompt = f"Gere um alerta divertido e empolgante dizendo que a partida {j['mandante']} x {j['visitante']} começará em 3 horas."
                        texto = analisador.perguntar_ao_gemini(prompt)
                        comandos.bot.send_message(chat_id, f"🔥 <b>VAR REGRESSIVO - 3 HORAS</b>\n\n{texto}", message_thread_id=topico_pre, parse_mode="HTML")
                        ALERTAS_ENVIADOS[match_id]["3h"] = True

                    # Alerta de 2 Horas
                    elif 110 <= minutos_restantes <= 120 and not ALERTAS_ENVIADOS[match_id]["2h"]:
                        prompt = f"Gere um alerta tático curto informando que o jogo {j['mandante']} x {j['visitante']} começará em 2 horas."
                        texto = analisador.perguntar_ao_gemini(prompt)
                        comandos.bot.send_message(chat_id, f"⚠️ <b>VAR REGRESSIVO - 2 HORAS</b>\n\n{texto}", message_thread_id=topico_pre, parse_mode="HTML")
                        ALERTAS_ENVIADOS[match_id]["2h"] = True

                    # Alerta de 1 Hora - ENVIA O DOSSIÊ COMPLETO COM PRECIFICAÇÃO E PROJEÇÕES SECUNDÁRIAS
                    elif 50 <= minutos_restantes <= 60 and not ALERTAS_ENVIADOS[match_id]["1h"]:
                        prompt = (
                            f"Crie um Dossiê Técnico Completo de Inteligência para a partida {j['mandante']} x {j['visitante']} pela {j['liga']}.\n"
                            "Gere o dossiê contendo:\n"
                            "1. Uma simulação clara da precificação por Poisson para as probabilidades do jogo e odds justas.\n"
                            "2. As projeções dos mercados secundários de cartões e escanteios com base nas tendências das equipes.\n"
                            "3. Uma recomendação de aposta com valor esperado positivo (+EV) justificando a entrada e aplicando o Critério de Kelly Fracionário.\n"
                            "Diretriz: Nunca utilize asteriscos no texto em hipótese alguma."
                        )
                        texto = analisador.perguntar_ao_gemini(prompt)
                        comandos.bot.send_message(chat_id, f"📊 <b>DOSSIÊ TÉCNICO VAR DO LUCRO (+EV)</b>\n\n{texto}", message_thread_id=topico_pre, parse_mode="HTML")
                        ALERTAS_ENVIADOS[match_id]["1h"] = True

                    # Alerta de 10 minutos
                    elif 5 <= minutos_restantes <= 10 and not ALERTAS_ENVIADOS[match_id]["10m"]:
                        prompt = f"Gere uma chamada imediata curta avisando que as equipes de {j['mandante']} e {j['visitante']} já estão em campo e a partida se iniciará em instantes."
                        texto = analisador.perguntar_ao_gemini(prompt)
                        comandos.bot.send_message(chat_id, f"🚨 <b>VAR REGRESSIVO - ENTRADA EM CAMPO</b>\n\n{texto}", message_thread_id=topico_pre, parse_mode="HTML")
                        ALERTAS_ENVIADOS[match_id]["10m"] = True

        except Exception as e:
            print(f"[ERRO AGENDADOR] Falha na execução da rotina interna do loop: {str(e)}")

        time.sleep(60)

# ==========================================
# THREAD 2: INICIALIZAÇÃO E CONTROLE
# ==========================================

def iniciar_bot_polling():
    """Inicia a thread dedicada para o polling contínuo do Telegram."""
    print("[THREAD POLLING] Bot de mensagens iniciado com sucesso.")
    while True:
        try:
            comandos.bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"[ERRO POLLING] Falha na conexão com o Telegram: {str(e)}")
            time.sleep(10)

if __name__ == "__main__":
    # Carrega dados do dia em memória imediatamente ao iniciar o app
    try:
        analisador.obter_jogos_do_dia(forcar=True)
    except Exception as e:
        print(f"[ERRO INICIAL] Falha ao carregar cache de jogos: {str(e)}")

    # Executa a thread de polling do telegram (Daemon)
    t_bot = threading.Thread(target=iniciar_bot_polling, daemon=True)
    t_bot.start()

    # Executa a thread do agendador e dos alertas regressivos (Daemon)
    t_agendador = threading.Thread(target=loop_tarefas_agendadas, daemon=True)
    t_agendador.start()

    # O Flask roda na thread principal para satisfazer a porta do Render instantaneamente
    porta = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=porta)