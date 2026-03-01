import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import os

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "1.0"
DATE_FILE = datetime.now().strftime("%d_%m_%Y")
DB_PATH = 'gv2_data.db'

# Couleurs prioritaires
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

def get_dynamic_colors():
    conn = get_connection()
    c_df = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    l_df = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    db_colors = pd.concat([c_df, l_df]).set_index('nom')['couleur'].to_dict()
    return {**FORCED_COLORS, **db_colors}

# --- BARRE LATÉRALE ---
if os.path.exists("logo_gv2.png"):
    st.sidebar.image("logo_gv2.png", use_container_width=True)
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Aide & Infos"])

# --- 1. ENCODAGE ---
if menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    collabs = pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()
    clients = pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    
    if not collabs or not clients:
        st.warning("⚠️ Les listes sont vides. Importez un CSV ou ajoutez-les manuellement dans **Paramètres**.")
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            d = st.date_input("Date", format="DD/MM/YYYY")
            cli = st.selectbox("Client", [""] + clients)
            col = st.selectbox("Collaborateur", [""] + collabs)
        with c2:
            t = st.number_input("Temps (h)", min_value=0.0, step=0.25)
            tc = st.number_input("Tarif Client (€)", value=80.0)
            ti = st.number_input("Tarif Interne (€)", value=45.0)
        desc = st.text_area("Description")
        ref = st.text_input("Référence Mission")
        
        if st.button("🚀 ENREGISTRER", type="primary", use_container_width=True):
            if cli and col and t > 0:
                conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                             (d.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                conn.commit()
                st.success("Enregistré !")
            else: st.error("Champs manquants.")

# --- 2. DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    if not df.empty:
        df['date_dt'] = pd.to_datetime(df['date'].str.replace('-', '/'), format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_dt'])
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y')
        sel_m = st.sidebar.multiselect("Mois", sorted(df['Mois_Label'].unique(), reverse=True), default=df['Mois_Label'].unique())
        df_f = df[df['Mois_Label'].isin(sel_m)]
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Heures", f"{df_f['temps'].sum():.2f} h")
            k2.metric("CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=get_dynamic_colors()), use_container_width=True)

# --- 4. PARAMÈTRES (SYNC AUTO) ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    t_maint, t_lists, t_csv = st.tabs(["💾 Maintenance", "👥 Listes & Couleurs", "📥 Import CSV"])
    
    with t_lists:
        col1, col2 = st.columns(2)
        for i, (title, table, d_col) in enumerate([("Collaborateurs", "collaborateurs", "#3498db"), ("Clients", "clients", "#e67e22")]):
            with [col1, col2][i]:
                st.subheader(title)
                with st.form(f"f_{table}", clear_on_submit=True):
                    n = st.text_input(f"Ajouter {title}")
                    if st.form_submit_button("OK"):
                        if n: conn.execute(f"INSERT OR IGNORE INTO {table} (nom, couleur) VALUES (?,?)", (n.strip(), d_col)); conn.commit(); st.rerun()
                for r in conn.execute(f"SELECT id, nom, couleur FROM {table} ORDER BY nom").fetchall():
                    c = st.columns([3, 1, 1])
                    c[0].write(r[1])
                    nc = c[1].color_picker("Col", r[2], key=f"p_{table}_{r[0]}", label_visibility="collapsed")
                    if nc != r[2]: conn.execute(f"UPDATE {table} SET couleur=? WHERE id=?", (nc, r[0])); conn.commit(); st.rerun()
                    if c[2].button("🗑️", key=f"d_{table}_{r[0]}"): conn.execute(f"DELETE FROM {table} WHERE id=?", (r[0],)); conn.commit(); st.rerun()

    with t_csv:
        st.subheader("📥 Import CSV avec Synchronisation des listes")
        up_csv = st.file_uploader("Fichier CSV", type="csv")
        if up_csv:
            df_raw = pd.read_csv(up_csv, sep=';', engine='python')
            mapping = {'date': 'Date', 'collab': 'collab', 'client': 'Nom du client', 'description': 'Description', 'mission_ref': 'Référence de mission', 'temps': 'Temps de travail', 'tarif_client': 'Tarif horaire client', 'fact_client': 'Facturation horaire client', 'tarif_interne': 'Tarif horaire interne GV2', 'fact_interne': 'Facturation interne GV2'}
            df_imp = df_raw[[v for v in mapping.values() if v in df_raw.columns]].rename(columns={v: k for k, v in mapping.items()})
            
            if st.button("✅ Lancer l'importation et synchroniser"):
                # 1. Nettoyage
                if 'date' in df_imp.columns: df_imp['date'] = df_imp['date'].astype(str).str.replace('-', '/')
                for col in ['temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']:
                    if col in df_imp.columns:
                        df_imp[col] = df_imp[col].astype(str).str.replace('€', '').str.replace(',', '.').str.replace('\xa0', '').str.strip()
                        df_imp[col] = pd.to_numeric(df_imp[col], errors='coerce').fillna(0)

                # 2. SYNCHRONISATION DES COLLABS ET CLIENTS
                if 'collab' in df_imp.columns:
                    for c in df_imp['collab'].unique():
                        conn.execute("INSERT OR IGNORE INTO collaborateurs (nom, couleur) VALUES (?,?)", (str(c), "#3498db"))
                if 'client' in df_imp.columns:
                    for cl in df_imp['client'].unique():
                        conn.execute("INSERT OR IGNORE INTO clients (nom, couleur) VALUES (?,?)", (str(cl), "#e67e22"))
                
                # 3. Import des prestations
                df_imp.to_sql('prestations', conn, if_exists='append', index=False)
                conn.commit()
                st.success(f"Terminé ! {len(df_imp)} lignes ajoutées. Les clients et collaborateurs ont été créés s'ils étaient nouveaux.")
                st.balloons(); st.rerun()

# --- MAINTENANCE & GESTION ---
elif menu == "🛠️ Gestion":
    st.header("🛠️ Gestion")
    df_g = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", get_connection())
    st.data_editor(df_g, disabled=["id"])
elif menu == "ℹ️ Aide & Infos":
    st.write("Version 1.0 - Auto-Sync Edition")
