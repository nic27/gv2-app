import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import re
import os

# --- CONFIGURATION & BDD ---
st.set_page_config(
    page_title="GV2 Management System", 
    layout="wide", 
    page_icon="logo_gv2.png"
)

VERSION = "1.3"
TODAY = datetime.now().strftime("%d/%m/%Y")

def get_connection():
    return sqlite3.connect('gv2_data.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prestations 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, collab TEXT, client TEXT, 
                  description TEXT, mission_ref TEXT, temps REAL, 
                  tarif_client REAL, fact_client REAL, 
                  tarif_interne REAL, fact_interne REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, tarif_defaut REAL, couleur TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collaborateurs (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    conn.commit()

init_db()

# --- FONCTIONS UTILITAIRES ---
def get_color_map():
    conn = get_connection()
    collabs = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    clients = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    return pd.concat([collabs, clients]).dropna(subset=['couleur']).set_index('nom')['couleur'].to_dict()

def clean_val(x):
    if pd.isna(x) or x == "/": return 0.0
    s = str(x).replace(',', '.').replace('€', '').strip()
    s = re.sub(r'[^0-9.]', '', s)
    try: return float(s)
    except: return 0.0

@st.dialog("Confirmer la suppression")
def confirm_delete_dialog(ids_to_delete):
    st.warning(f"⚠️ Supprimer définitivement {len(ids_to_delete)} ligne(s) ?")
    c1, c2 = st.columns(2)
    if c1.button("🔥 Oui, supprimer", type="primary", use_container_width=True):
        conn = get_connection()
        conn.executemany("DELETE FROM prestations WHERE id = ?", [(x,) for x in ids_to_delete])
        conn.commit()
        st.success("Supprimé.")
        st.rerun()
    if c2.button("Annuler", use_container_width=True):
        st.rerun()

# --- BARRE LATÉRALE ---
if os.path.exists("logo_gv2.png"):
    st.sidebar.image("logo_gv2.png", use_container_width=True)

st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION} | **Date :** {TODAY}")
st.sidebar.divider()

menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres"])

# --- PAGES ---
if menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    clients_list = [""] + pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    collabs_list = [""] + pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            d_obj = st.date_input("Date", value=None, format="DD/MM/YYYY")
            cli = st.selectbox("Client", clients_list)
            col = st.selectbox("Collaborateur", collabs_list)
        with c2:
            t = st.number_input("Temps (h)", min_value=0.0, step=0.25)
            tc = st.number_input("Tarif Client (€)", value=80.0)
            ti = st.number_input("Tarif Interne (€)", value=45.0)
        desc = st.text_area("Description")
        ref = st.text_input("Référence Mission")

        if st.button("🔍 Vérifier", use_container_width=True):
            if not d_obj or cli == "" or col == "" or t <= 0:
                st.error("Champs obligatoires manquants.")
            else:
                st.session_state.confirm_data = {"date": d_obj.strftime("%d/%m/%Y"), "collab": col, "client": cli, "description": desc, "mission_ref": ref, "temps": t, "tarif_client": tc, "fact_client": t * tc, "tarif_interne": ti, "fact_interne": t * ti}

    if "confirm_data" in st.session_state:
        d = st.session_state.confirm_data
        st.info(f"Confirmer l'ajout pour {d['client']} ?")
        if st.button("🚀 ENREGISTRER", type="primary", use_container_width=True):
            conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", (d['date'], d['collab'], d['client'], d['description'], d['mission_ref'], d['temps'], d['tarif_client'], d['fact_client'], d['tarif_interne'], d['fact_interne']))
            conn.commit(); st.success("Enregistré !"); del st.session_state.confirm_data; st.rerun()

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard Analytique")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    if not df.empty:
        df['fact_client'] = df['fact_client'].fillna(0)
        st.metric("Total CA HT", f"{df['fact_client'].sum():,.2f} €")
        st.plotly_chart(px.bar(df.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', title="CA par Client"), use_container_width=True)
        
        # Export CSV des données filtrées
        csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 Télécharger les données en CSV", csv, "export_data.csv", "text/csv")
    else: st.info("Aucune donnée disponible.")

elif menu == "🛠️ Gestion":
    st.header("🛠️ Modification des entrées")
    conn = get_connection()
    df_edit = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    if not df_edit.empty:
        df_edit.insert(0, '🗑️', False)
        edited = st.data_editor(df_edit, disabled=["id"], hide_index=True)
        if st.button("💾 Appliquer les modifications"):
            for _, r in edited[edited['🗑️'] == False].iterrows():
                conn.execute("UPDATE prestations SET date=?, collab=?, client=?, description=?, temps=? WHERE id=?", (r['date'], r['collab'], r['client'], r['description'], r['temps'], r['id']))
            conn.commit(); st.success("Mis à jour !"); st.rerun()
        
        to_del = edited[edited['🗑️'] == True]
        if not to_del.empty and st.button("🔥 Supprimer la sélection"):
            confirm_delete_dialog(to_del['id'].tolist())

elif menu == "⚙️ Paramètres":
    st.header("⚙️ Paramètres & Sauvegarde")
    
    # --- NOUVELLE SECTION SAUVEGARDE COMPLÈTE ---
    with st.container(border=True):
        st.subheader("💾 Sauvegarde de sécurité")
        st.write("Téléchargez l'intégralité de la base de données (`gv2_data.db`). Ce fichier contient toutes vos prestations, clients et collaborateurs.")
        
        if os.path.exists("gv2_data.db"):
            with open("gv2_data.db", "rb") as f:
                db_binary = f.read()
            
            file_name = f"backup_gv2_full_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
            st.download_button(
                label="📥 Télécharger la base de données (.db)",
                data=db_binary,
                file_name=file_name,
                mime="application/x-sqlite3",
                use_container_width=True,
                help="Ce fichier peut être réutilisé pour restaurer l'application en cas de problème."
            )
        else:
            st.error("Fichier de base de données introuvable.")

    st.divider()
    # Sections Clients/Collabs
    st.subheader("👥 Gestion des intervenants et clients")
    # ... (le reste de votre code pour ajouter clients/collabs)
