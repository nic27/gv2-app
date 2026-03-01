import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import os

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "1.4"
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

def get_dynamic_colors():
    conn = get_connection()
    c_df = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    l_df = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    db_colors = pd.concat([c_df, l_df]).set_index('nom')['couleur'].to_dict()
    return {**db_colors, **FORCED_COLORS}

# --- NAVIGATION ---
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Aide & Infos"])

# --- 2. DASHBOARD (TRI CHRONOLOGIQUE RÉPARÉ) ---
if menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    
    if not df.empty:
        # 1. Conversion propre pour le tri
        df['date_dt'] = pd.to_datetime(df['date'].str.replace('-', '/'), format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_dt'])
        
        # Création de colonnes de tri
        df['Année'] = df['date_dt'].dt.year
        df['Mois_Tri'] = df['date_dt'].dt.strftime('%Y-%m') # Pour le tri technique (2025-09)
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y') # Pour l'affichage (09/2025)

        st.sidebar.header("🔍 Filtres")
        
        # Filtre Année
        years = sorted(df['Année'].unique(), reverse=True)
        sel_y = st.sidebar.multiselect("Années", years, default=years)
        
        # Filtre Mois - On trie par Mois_Tri pour avoir l'ordre chrono
        mask_y = df[df['Année'].isin(sel_y)]
        month_order = mask_y.sort_values('date_dt', ascending=False)
        available_months = month_order['Mois_Label'].unique().tolist()
        
        sel_m = st.sidebar.multiselect("Mois", available_months, default=available_months)
        
        # Autres Filtres
        sel_co = st.sidebar.multiselect("Collaborateurs", sorted(df['collab'].unique()), default=df['collab'].unique())
        sel_cl = st.sidebar.multiselect("Clients", sorted(df['client'].unique()), default=df['client'].unique())
        
        # Application finale
        df_f = df[
            (df['Année'].isin(sel_y)) & 
            (df['Mois_Label'].isin(sel_m)) & 
            (df['collab'].isin(sel_co)) & 
            (df['client'].isin(sel_cl))
        ]
        
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Heures", f"{df_f['temps'].sum():.2f} h")
            k2.metric("CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), 
                                   x='client', y='fact_client', color='client', 
                                   color_discrete_map=get_dynamic_colors(),
                                   title="Chiffre d'Affaires par Client"), use_container_width=True)
            
            st.plotly_chart(px.line(df_f.groupby('Mois_Tri')['fact_client'].sum().reset_index(), 
                                    x='Mois_Tri', y='fact_client', title="Évolution mensuelle"), use_container_width=True)
        else:
            st.warning("Sélection vide.")
    else:
        st.info("Aucune donnée.")

# --- 1. ENCODAGE (SANS PRÉ-REMPLISSAGE) ---
elif menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    collabs = [""] + pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()
    clients = [""] + pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    
    with st.form("form_encodage", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            d = st.date_input("Date", format="DD/MM/YYYY")
            cli = st.selectbox("Client", clients, index=0)
            col = st.selectbox("Collaborateur", collabs, index=0)
        with c2:
            t = st.number_input("Temps (h)", min_value=0.0, step=0.25, value=0.0)
            tc = st.number_input("Tarif Client (€)", min_value=0.0, value=0.0)
            ti = st.number_input("Tarif Interne (€)", min_value=0.0, value=0.0)
        desc = st.text_area("Description / Détails")
        ref = st.text_input("Référence Mission")
        
        if st.form_submit_button("🚀 ENREGISTRER", use_container_width=True):
            if cli != "" and col != "" and t > 0:
                conn.execute("INSERT INTO prestations (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                             (d.strftime("%d/%m/%Y"), col, cli, desc, ref, t, tc, t*tc, ti, t*ti))
                conn.commit()
                st.success("Enregistré !")
                st.balloons()
            else: st.error("Veuillez remplir Client, Collaborateur et Temps.")

# --- 4. PARAMÈTRES (MAINTENANCE RÉTABLIE) ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    t_maint, t_lists, t_csv = st.tabs(["💾 Maintenance", "👥 Listes & Couleurs", "📥 Import CSV"])
    
    with t_maint:
        c1, c2 = st.columns(2)
        with c1:
            if os.path.exists(DB_PATH):
                with open(DB_PATH, "rb") as f:
                    st.download_button(f"📥 Télécharger Backup .db", f, f"backup_gv2_{DATE_FILE}.db")
        with c2:
            up_db = st.file_uploader("Restaurer .db", type="db")
            if up_db and st.button("🔥 Lancer Restauration"):
                with open(DB_PATH, "wb") as f: f.write(up_db.getbuffer())
                st.rerun()

    with t_lists:
        col1, col2 = st.columns(2)
        for i, (title, table, def_col) in enumerate([("Collaborateurs", "collaborateurs", "#3498db"), ("Clients", "clients", "#e67e22")]):
            with [col1, col2][i]:
                st.subheader(title)
                with st.form(f"f_{table}", clear_on_submit=True):
                    n = st.text_input(f"Ajouter {title[:-1]}")
                    if st.form_submit_button("Ajouter"):
                        if n: conn.execute(f"INSERT OR IGNORE INTO {table} (nom, couleur) VALUES (?,?)", (n.strip(), FORCED_COLORS.get(n.strip(), def_col))); conn.commit(); st.rerun()
                for r in conn.execute(f"SELECT id, nom, couleur FROM {table} ORDER BY nom").fetchall():
                    c = st.columns([3, 1, 1])
                    c[0].write(r[1]); nc = c[1].color_picker("C", r[2], key=f"cp_{table}_{r[0]}", label_visibility="collapsed")
                    if nc != r[2]: conn.execute(f"UPDATE {table} SET couleur=? WHERE id=?", (nc, r[0])); conn.commit(); st.rerun()
                    if c[2].button("🗑️", key=f"d_{table}_{r[0]}"): conn.execute(f"DELETE FROM {table} WHERE id=?", (r[0],)); conn.commit(); st.rerun()

    with t_csv:
        st.subheader("📥 Import CSV")
        up_csv = st.file_uploader("Fichier CSV", type="csv")
        if up_csv:
            df_raw = pd.read_csv(up_csv, sep=';', engine='python')
            mapping = {'date': 'Date', 'collab': 'collab', 'client': 'Nom du client', 'description': 'Description', 'mission_ref': 'Référence de mission', 'temps': 'Temps de travail', 'tarif_client': 'Tarif horaire client', 'fact_client': 'Facturation horaire client', 'tarif_interne': 'Tarif horaire interne GV2', 'fact_interne': 'Facturation interne GV2'}
            df_imp = df_raw[[v for v in mapping.values() if v in df_raw.columns]].rename(columns={v: k for k, v in mapping.items()})
            if st.button("✅ Lancer l'importation"):
                if 'date' in df_imp.columns: df_imp['date'] = df_imp['date'].astype(str).str.replace('-', '/')
                for col in ['temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']:
                    if col in df_imp.columns:
                        df_imp[col] = df_imp[col].astype(str).str.replace('€', '').str.replace(',', '.').str.replace('\xa0', '').str.strip()
                        df_imp[col] = pd.to_numeric(df_imp[col], errors='coerce').fillna(0)
                for c in df_imp['collab'].unique(): conn.execute("INSERT OR IGNORE INTO collaborateurs (nom, couleur) VALUES (?,?)", (str(c), FORCED_COLORS.get(str(c), "#3498db")))
                for cl in df_imp['client'].unique(): conn.execute("INSERT OR IGNORE INTO clients (nom, couleur) VALUES (?,?)", (str(cl), FORCED_COLORS.get(str(cl), "#e67e22")))
                df_imp.to_sql('prestations', conn, if_exists='append', index=False); conn.commit()
                st.success("Import réussi !"); st.balloons(); st.rerun()

# --- GESTION ---
elif menu == "🛠️ Gestion":
    st.header("🛠️ Gestion")
    df_g = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", get_connection())
    edited_df = st.data_editor(df_g, disabled=["id"])
    if st.button("💾 Sauvegarder"):
        edited_df.to_sql('prestations', get_connection(), if_exists='replace', index=False)
        st.success("Mise à jour OK !")
elif menu == "ℹ️ Aide & Infos":
    st.write("GV2 Management - Version 1.4")
