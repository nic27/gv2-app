import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import os

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "1.7"
DATE_FILE = datetime.now().strftime("%d_%m_%Y")
DB_PATH = 'gv2_data.db'

FORCED_COLORS = {
    "JC": "#E22F2F", "Ludo": "#2A33C3", "Nico": "#20DC46",
    "Skydiving Promotion": "#161515", "Sourse": "#C03BD6", "Stemme Belgium": "#999999"
}

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prestations 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, collab TEXT, client TEXT, 
                  description TEXT, mission_ref TEXT, temps REAL, 
                  tarif_client REAL, fact_client REAL, 
                  tarif_interne REAL, fact_interne REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collaborateurs (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    conn.commit()

init_db()

# --- NAVIGATION ---
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Aide & Infos"])

# --- 3. GESTION (SUPPRESSION ACTIVÉE) ---
if menu == "🛠️ Gestion":
    st.header("🛠️ Gestion des prestations")
    st.info("💡 Pour supprimer : sélectionnez une ou plusieurs lignes (clic à gauche) puis appuyez sur la touche 'Suppr' de votre clavier, ou utilisez l'icône poubelle qui apparaît à droite lors de la sélection.")
    
    conn = get_connection()
    df_g = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", conn)
    
    if not df_g.empty:
        # num_rows="dynamic" permet d'ajouter/supprimer des lignes
        edited_df = st.data_editor(
            df_g, 
            num_rows="dynamic", 
            use_container_width=True,
            disabled=["id"], # On ne touche pas aux IDs
            key="prestation_editor"
        )
        
        c1, c2 = st.columns([1, 4])
        if c1.button("💾 Sauvegarder les changements", type="primary"):
            try:
                # On remplace toute la table par le contenu de l'éditeur (inclut suppressions)
                edited_df.to_sql('prestations', conn, if_exists='replace', index=False)
                st.success("Modifications et suppressions enregistrées !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la sauvegarde : {e}")
    else:
        st.write("Aucune prestation enregistrée.")

# --- 1. ENCODAGE (AVEC MISSION_REF) ---
elif menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    collabs = [""] + pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()
    clients = [""] + pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    
    with st.form("f_encodage", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            d = st.date_input("Date", format="DD/MM/YYYY")
            cli = st.selectbox("Client", clients, index=0)
            col = st.selectbox("Collaborateur", collabs, index=0)
            ref = st.text_input("Référence Mission")
        with c2:
            t = st.number_input("Temps (h)", min_value=0.0, step=0.25, value=0.0)
            tc = st.number_input("Tarif Client (€)", min_value=0.0, value=0.0)
            ti = st.number_input("Tarif Interne (€)", min_value=0.0, value=0.0)
        desc = st.text_area("Description")
        
        if st.form_submit_button("🚀 ENREGISTRER"):
            if cli and col and t > 0:
                conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                             (d.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                conn.commit()
                st.success("Prestation ajoutée !")
                st.balloons()
            else: st.error("Veuillez remplir les champs obligatoires.")

# --- 2. DASHBOARD (AVEC TOUS LES FILTRES) ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    if not df.empty:
        df['date_dt'] = pd.to_datetime(df['date'].str.replace('-', '/'), format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_dt'])
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y')
        df['Année'] = df['date_dt'].dt.year

        st.sidebar.header("🔍 Filtres")
        sel_y = st.sidebar.multiselect("Années", sorted(df['Année'].unique(), reverse=True), default=df['Année'].unique())
        sel_co = st.sidebar.multiselect("Collaborateurs", sorted(df['collab'].unique()), default=df['collab'].unique())
        sel_cl = st.sidebar.multiselect("Clients", sorted(df['client'].unique()), default=df['client'].unique())
        
        df_f = df[(df['Année'].isin(sel_y)) & (df['collab'].isin(sel_co)) & (df['client'].isin(sel_cl))]
        
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Heures", f"{df_f['temps'].sum():.2f} h")
            k2.metric("CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', title="CA par client"), use_container_width=True)
    else: st.info("Base vide.")

# --- 4. PARAMÈTRES (MAINTENANCE) ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    t_maint, t_lists = st.tabs(["💾 Maintenance", "👥 Listes & Couleurs"])
    
    with t_maint:
        st.subheader("Backup & Restauration")
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as f:
                st.download_button(f"📥 Backup .db", f, f"gv2_backup.db")
        up_db = st.file_uploader("Restaurer .db", type="db")
        if up_db and st.button("🔥 Confirmer Restauration"):
            with open(DB_PATH, "wb") as f: f.write(up_db.getbuffer())
            st.rerun()

    with t_lists:
        # Code gestion manuelle des listes
        st.write("Gérez vos collaborateurs et clients ici.")
