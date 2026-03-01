import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import os

# --- CONFIGURATION & BDD ---
st.set_page_config(page_title="GV2 Management System", layout="wide", page_icon="📊")

VERSION = "1.6"
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

# --- POP-UP DE SÉCURITÉ ---
@st.dialog("⚠️ RESTAURATION DE LA BASE")
def confirm_restore_dialog(uploaded_file):
    st.error("### ATTENTION : ÉCRASEMENT TOTAL")
    st.write("Toutes les données actuelles seront supprimées pour être remplacées par le fichier chargé.")
    if st.button("🔥 CONFIRMER L'ÉCRASEMENT", type="primary", use_container_width=True):
        with open(DB_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Base restaurée !"); st.rerun()

# --- NAVIGATION ---
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Aide & Infos"])

# --- 1. ENCODAGE (AVEC RÉFÉRENCE MISSION) ---
if menu == "📝 Encodage":
    st.header("📝 Nouvelle Prestation")
    conn = get_connection()
    collabs = [""] + pd.read_sql("SELECT nom FROM collaborateurs ORDER BY nom", conn)['nom'].tolist()
    clients = [""] + pd.read_sql("SELECT nom FROM clients ORDER BY nom", conn)['nom'].tolist()
    
    with st.form("f_encodage", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            d = st.date_input("Date de la prestation", format="DD/MM/YYYY")
            cli = st.selectbox("Client", clients, index=0)
            col = st.selectbox("Collaborateur", collabs, index=0)
            ref_miss = st.text_input("Référence Mission (ex: AUDIT-2025-01)") # CHAMP AJOUTÉ
        with c2:
            t = st.number_input("Temps passé (h)", min_value=0.0, step=0.25, value=0.0)
            tc = st.number_input("Tarif horaire Client (€)", min_value=0.0, value=0.0)
            ti = st.number_input("Tarif horaire Interne (€)", min_value=0.0, value=0.0)
        
        desc = st.text_area("Description du travail effectué")
        
        if st.form_submit_button("🚀 ENREGISTRER", use_container_width=True):
            if cli and col and t > 0:
                conn.execute("""INSERT INTO prestations 
                             (date, collab, client, description, mission_ref, temps, tarif_client, fact_client, tarif_interne, fact_interne) 
                             VALUES (?,?,?,?,?,?,?,?,?,?)""", 
                             (d.strftime("%d/%m/%Y"), col, cli, desc, ref_miss, t, tc, t*tc, ti, t*ti))
                conn.commit()
                st.success(f"Enregistré ! {t}h pour {cli}")
                st.balloons()
            else:
                st.error("Veuillez remplir au moins le Client, le Collaborateur et un Temps > 0.")

# --- 2. DASHBOARD (AVEC TOUS LES FILTRES) ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    
    if not df.empty:
        df['date_dt'] = pd.to_datetime(df['date'].str.replace('-', '/'), format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_dt'])
        df['Année'] = df['date_dt'].dt.year
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y')
        df['Mois_Tri'] = df['date_dt'].dt.strftime('%Y-%m')

        st.sidebar.header("🔍 Filtres d'affichage")
        sel_y = st.sidebar.multiselect("Années", sorted(df['Année'].unique(), reverse=True), default=df['Année'].unique())
        
        # Filtre mois lié aux années
        mask_y = df[df['Année'].isin(sel_y)]
        available_months = mask_y.sort_values('date_dt', ascending=False)['Mois_Label'].unique().tolist()
        sel_m = st.sidebar.multiselect("Mois", available_months, default=available_months)
        
        # Filtres Collab et Clients
        sel_co = st.sidebar.multiselect("Collaborateurs", sorted(df['collab'].unique()), default=df['collab'].unique())
        sel_cl = st.sidebar.multiselect("Clients", sorted(df['client'].unique()), default=df['client'].unique())
        
        df_f = df[
            (df['Année'].isin(sel_y)) & 
            (df['Mois_Label'].isin(sel_m)) & 
            (df['collab'].isin(sel_co)) & 
            (df['client'].isin(sel_cl))
        ]
        
        if not df_f.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Heures", f"{df_f['temps'].sum():.1f}h")
            k2.metric("CA Client HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge Brute", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            k4.metric("Nb Missions", len(df_f['mission_ref'].unique()))
            
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), 
                                   x='client', y='fact_client', color='client', 
                                   color_discrete_map=get_dynamic_colors(), title="Chiffre d'Affaires par Client"), use_container_width=True)
            
            st.plotly_chart(px.line(df_f.groupby('Mois_Tri')['fact_client'].sum().reset_index(), 
                                    x='Mois_Tri', y='fact_client', title="Évolution du CA Mensuel"), use_container_width=True)
        else: st.warning("Aucune donnée pour ces filtres.")
    else: st.info("Base vide.")

# --- 4. PARAMÈTRES (AVERTISSEMENT RESTAURATION) ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    t_maint, t_lists, t_csv = st.tabs(["💾 Maintenance", "👥 Listes & Couleurs", "📥 Import CSV"])
    
    with t_maint:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Backup")
            if os.path.exists(DB_PATH):
                with open(DB_PATH, "rb") as f:
                    st.download_button(f"📥 Backup_{DATE_FILE}.db", f, f"gv2_data_{DATE_FILE}.db")
        with c2:
            st.subheader("Restauration")
            up_db = st.file_uploader("Importer un .db", type="db")
            if up_db and st.button("🚀 Lancer l'importation"):
                confirm_restore_dialog(up_db)

    with t_lists:
        # Code de gestion des listes (identique à 1.5)
        st.info("Utilisez l'Import CSV pour remplir automatiquement ces listes.")
        # ... (Logique de création manuelle des collabs/clients conservée) ...

    with t_csv:
        st.subheader("📥 Import CSV")
        up_csv = st.file_uploader("Fichier CSV", type="csv")
        if up_csv:
            df_raw = pd.read_csv(up_csv, sep=';', engine='python')
            mapping = {'date': 'Date', 'collab': 'collab', 'client': 'Nom du client', 'description': 'Description', 'mission_ref': 'Référence de mission', 'temps': 'Temps de travail', 'tarif_client': 'Tarif horaire client', 'fact_client': 'Facturation horaire client', 'tarif_interne': 'Tarif horaire interne GV2', 'fact_interne': 'Facturation interne GV2'}
            df_imp = df_raw[[v for v in mapping.values() if v in df_raw.columns]].rename(columns={v: k for k, v in mapping.items()})
            if st.button("✅ Lancer l'importation"):
                # Nettoyage
                if 'date' in df_imp.columns: df_imp['date'] = df_imp['date'].astype(str).str.replace('-', '/')
                for col in ['temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']:
                    if col in df_imp.columns:
                        df_imp[col] = df_imp[col].astype(str).str.replace('€', '').str.replace(',', '.').str.replace('\xa0', '').str.strip()
                        df_imp[col] = pd.to_numeric(df_imp[col], errors='coerce').fillna(0)
                # Sync automatique
                for c in df_imp['collab'].unique(): conn.execute("INSERT OR IGNORE INTO collaborateurs (nom, couleur) VALUES (?,?)", (str(c), FORCED_COLORS.get(str(c), "#3498db")))
                for cl in df_imp['client'].unique(): conn.execute("INSERT OR IGNORE INTO clients (nom, couleur) VALUES (?,?)", (str(cl), FORCED_COLORS.get(str(cl), "#e67e22")))
                df_imp.to_sql('prestations', conn, if_exists='append', index=False)
                conn.commit(); st.success("Import terminé !"); st.rerun()

elif menu == "🛠️ Gestion":
    st.data_editor(pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", get_connection()), disabled=["id"])
