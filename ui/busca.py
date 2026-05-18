"""
Interface de busca de negativações - Streamlit (gratuito)

Instalação:
    pip install streamlit requests

Execução:
    streamlit run ui/busca.py
"""
import streamlit as st
import requests
from datetime import datetime

API_URL = st.sidebar.text_input("URL da API", value="http://localhost:8000")

st.set_page_config(
    page_title="Negativações Compartilhadas",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Negativações Compartilhadas")
st.caption("Busca inteligente de evidências de negativação no Pipefy")


# ── Busca principal ────────────────────────────────────────────────────────────
st.subheader("Buscar marca")
col_input, col_btn = st.columns([4, 1])

with col_input:
    query = st.text_input("", placeholder="Ex: Serasa, Acordo Certo, Boa Compra...", label_visibility="collapsed")

with col_btn:
    buscar = st.button("Buscar", use_container_width=True, type="primary")

if buscar and query:
    with st.spinner("Buscando..."):
        try:
            r = requests.get(f"{API_URL}/search", params={"q": query, "limite": 30}, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            st.error(f"Erro ao conectar na API: {e}")
            st.stop()

    # ── Marcas encontradas ─────────────────────────────────────────────────────
    if data["marcas"]:
        for marca in data["marcas"]:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"### {marca['nome']}")
                    if marca.get("nome_mysql"):
                        st.caption(f"MySQL: `{marca['nome_mysql']}`")
                with col2:
                    st.metric("Negativações realizadas", marca["negativacoes_realizadas"])
                with col3:
                    st.metric("Negativações recebidas", marca["negativacoes_recebidas"])

                # Grupo empresarial
                if marca.get("grupo"):
                    grupo = marca["grupo"]
                    outras = [m["nome"] for m in grupo.get("outras_marcas", [])]
                    outras_str = ", ".join(outras) if outras else "nenhuma"
                    st.info(f"**Grupo empresarial:** {grupo['nome']} | Outras marcas: {outras_str}")

                # Boa fé
                if marca.get("boa_fe"):
                    st.markdown("**Boa fé mútua identificada:**")
                    for bf in marca["boa_fe"]:
                        st.success(
                            f"✅ {bf['marca_a']} ↔ {bf['marca_b']} "
                            f"| Plataforma: {bf.get('plataforma') or '—'}"
                        )

                # Cards relacionados
                if marca.get("cards_relacionados"):
                    with st.expander(f"Cards relacionados ({len(marca['cards_relacionados'])})"):
                        for card in marca["cards_relacionados"]:
                            link = f"[{card['titulo'] or card['id']}]({card['pipefy_url']})"
                            fase = card.get("fase") or "—"
                            plat = card.get("plataforma") or "—"
                            data_card = card.get("data") or "—"
                            st.markdown(f"- {link} | Fase: **{fase}** | Plataforma: {plat} | Data: {data_card}")
    else:
        st.warning(f"Nenhuma marca encontrada para '{query}' no banco.")

    # ── Evidências semânticas ──────────────────────────────────────────────────
    if data["evidencias_semanticas"]:
        st.divider()
        st.subheader(f"Evidências encontradas ({data['total_evidencias']})")

        for ev in data["evidencias_semanticas"]:
            sim = ev.get("similaridade", 0)
            confirmada = ev.get("confirmacao_negativacao", False)
            cor = "🟢" if confirmada else "🟡"

            with st.expander(
                f"{cor} {ev.get('nome_logico') or ev.get('nome_original') or 'Sem nome'} "
                f"— similaridade: {sim:.0%}"
            ):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.markdown(f"**Marca:** {ev.get('marca_identificada') or '—'}")
                    st.markdown(f"**Concorrente:** {ev.get('concorrente_identificado') or '—'}")
                with col_b:
                    st.markdown(f"**Plataforma:** {ev.get('plataforma') or '—'}")
                    st.markdown(f"**Tipo:** {ev.get('tipo_evidencia') or '—'}")
                with col_c:
                    st.markdown(f"**Data:** {ev.get('data_evidencia') or '—'}")
                    conf = ev.get('confianca', 0)
                    st.markdown(f"**Confiança IA:** {conf:.0%}")

                st.markdown(f"**Card Pipefy:** [{ev['card_id']}](https://app.pipefy.com/open-cards/{ev['card_id']})")

                url_img = ev.get("url_cache") or ev.get("url_original")
                if url_img:
                    st.markdown(f"[Ver evidência original]({url_img})")
    else:
        st.info("Nenhuma evidência semântica encontrada.")


# ── Verificador de Boa Fé ──────────────────────────────────────────────────────
st.divider()
st.subheader("Verificar Boa Fé entre duas marcas")

col_bf1, col_bf2, col_bf3 = st.columns([2, 2, 1])
with col_bf1:
    marca_a = st.text_input("Marca A", placeholder="Ex: Serasa")
with col_bf2:
    marca_b = st.text_input("Marca B", placeholder="Ex: Acordo Certo")
with col_bf3:
    verificar = st.button("Verificar", use_container_width=True)

if verificar and marca_a and marca_b:
    with st.spinner("Verificando..."):
        try:
            r = requests.get(f"{API_URL}/boa-fe", params={"marca_a": marca_a, "marca_b": marca_b}, timeout=10)
            if r.status_code == 404:
                st.error("Uma ou ambas as marcas não estão na base de dados.")
            else:
                r.raise_for_status()
                bf = r.json()

                if bf["boa_fe_completa"]:
                    st.success("✅ **Boa fé completa!** Ambas as marcas já negativaram uma à outra.")
                else:
                    st.warning("⚠️ Boa fé **incompleta**.")

                col1, col2 = st.columns(2)
                with col1:
                    icone = "✅" if bf["a_negativou_b"] else "❌"
                    st.markdown(f"{icone} **{marca_a}** negativou **{marca_b}**")
                    for ev in bf.get("evidencias_a_negativou_b", []):
                        st.caption(
                            f"Card: {ev['card_id']} | {ev.get('plataforma') or '—'} | {ev.get('data') or '—'}"
                        )
                        if ev.get("evidencia_nome"):
                            st.caption(f"Evidência: {ev['evidencia_nome']}")

                with col2:
                    icone = "✅" if bf["b_negativou_a"] else "❌"
                    st.markdown(f"{icone} **{marca_b}** negativou **{marca_a}**")
                    for ev in bf.get("evidencias_b_negativou_a", []):
                        st.caption(
                            f"Card: {ev['card_id']} | {ev.get('plataforma') or '—'} | {ev.get('data') or '—'}"
                        )
                        if ev.get("evidencia_nome"):
                            st.caption(f"Evidência: {ev['evidencia_nome']}")

        except Exception as e:
            st.error(f"Erro: {e}")


# ── Painel admin: processar card manualmente ───────────────────────────────────
with st.sidebar:
    st.divider()
    st.subheader("Processar card")
    card_id_manual = st.text_input("ID do Card", placeholder="741065587")
    if st.button("Enfileirar para análise"):
        try:
            r = requests.post(f"{API_URL}/webhook/process/{card_id_manual}", timeout=10)
            r.raise_for_status()
            st.success(f"Card {card_id_manual} enfileirado!")
        except Exception as e:
            st.error(f"Erro: {e}")

    st.divider()
    st.caption("Negativações Compartilhadas v1.0")
