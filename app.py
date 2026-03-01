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
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, tarif_defaut REAL, couleur TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collaborateurs (id INTEGER PRIMARY KEY, nom TEXT UNIQUE, couleur TEXT)''')
    conn.commit()

init_db()

# --- FONCTIONS UTILITAIRES ---
def get_color_map():
    conn = get_connection()
    collabs_db = pd.read_sql("SELECT nom, couleur FROM collaborateurs", conn)
    clients_db = pd.read_sql("SELECT nom, couleur FROM clients", conn)
    db_colors = pd.concat([collabs_db, clients_db]).dropna(subset=['couleur']).set_index('nom')['couleur'].to_dict()
    return {**db_colors, **FORCED_COLORS}

def reset_form():
    for k in ["f_date", "f_client", "f_collab", "f_temps", "f_desc", "f_ref"]:
        if k in st.session_state:
            st.session_state[k] = None if k == "f_date" else "" if k != "f_temps" else 0.0
    if "submitted" in st.session_state:
        del st.session_state["submitted"]

# --- BARRE LATÉRALE ---
if os.path.exists("logo_gv2.png"):
    st.sidebar.image("logo_gv2.png", use_container_width=True)
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Aide & Infos"])

# --- 2. DASHBOARD (CORRECTION DATE) ---
if menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    cmap = get_color_map()
    if not df.empty:
        # Nettoyage Date : remplace "-" par "/" pour assurer la lecture
        df['date_clean'] = df['date'].str.replace('-', '/')
        df['date_dt'] = pd.to_datetime(df['date_clean'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
        
        # Supprimer les lignes dont la date est invalide
        df = df.dropna(subset=['date_dt'])
        
        df['Année'] = df['date_dt'].dt.year
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y')
        
        st.sidebar.header("🔍 Filtres")
        y_list = sorted(df['Année'].unique(), reverse=True)
        sel_y = st.sidebar.multiselect("Années", y_list, default=y_list)
        mois_options = df[df['Année'].isin(sel_y)].sort_values('date_dt', ascending=False)['Mois_Label'].unique()
        sel_m = st.sidebar.multiselect("Mois", mois_options, default=mois_options)
        sel_co = st.sidebar.multiselect("Collab", sorted(df['collab'].unique()), default=df['collab'].unique())
        sel_cl = st.sidebar.multiselect("Clients", sorted(df['client'].unique()), default=df['client'].unique())
        
        df_f = df[(df['Année'].isin(sel_y)) & (df['Mois_Label'].isin(sel_m)) & (df['collab'].isin(sel_co)) & (df['client'].isin(sel_cl))]
        
        if not df_f.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Heures", f"{df_f['temps'].sum():.2f} h")
            k2.metric("CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            k3.metric("Marge", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            
            csv = df_f.drop(columns=['date_clean', 'date_dt', 'Année', 'Mois_Label']).to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Exporter sélection (CSV)", csv, f"export_gv2_{DATE_FILE}.csv", "text/csv")
            
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=cmap), use_container_width=True)
        else: st.warning("Sélection vide. Vérifiez vos filtres.")
    else: st.info("Base vide.")

# --- 4. PARAMÈTRES (IMPORT CORRIGÉ) ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    tab_maint, tab_csv = st.tabs(["💾 Maintenance", "📥 Import CSV"])
    
    with tab_csv:
        st.subheader("📥 Importation CSV")
        up_csv = st.file_uploader("Choisir le fichier CSV", type="csv")
        if up_csv:
            df_imp = pd.read_csv(up_csv, sep=';', engine='python')
            
            mapping = {
                'date': ['Date', 'date'],
                'collab': ['collab', 'Collaborateur'],
                'client': ['Nom du client', 'client'],
                'description': ['Description', 'description'],
                'mission_ref': ['Référence de mission', 'mission_ref'],
                'temps': ['Temps de travail', 'temps'],
                'tarif_client': ['Tarif horaire client', 'tarif_client'],
                'fact_client': ['Facturation horaire client', 'fact_client'],
                'tarif_interne': ['Tarif horaire interne GV2', 'tarif_interne'],
                'fact_interne': ['Facturation interne GV2', 'fact_interne']
            }
            
            # Renommage
            new_cols = {}
            for db_col, candidates in mapping.items():
                for c in candidates:
                    if c in df_imp.columns: new_cols[c] = db_col
            df_imp = df_imp.rename(columns=new_cols)

            # --- NETTOYAGE CRITIQUE ---
            # 1. Dates : On force le format texte avec slashs
            if 'date' in df_imp.columns:
                df_imp['date'] = df_imp['date'].astype(str).str.replace('-', '/')

            # 2. Nombres : On vire les €, les espaces, et on remplace la virgule par un point
            num_cols = ['temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']
            for col in num_cols:
                if col in df_imp.columns:
                    df_imp[col] = df_imp[col].astype(str).str.replace('€', '').str.replace('\xa0', '').str.replace(',', '.').str.strip()
                    df_imp[col] = pd.to_numeric(df_imp[col], errors='coerce').fillna(0)

            st.write("Données prêtes à l'import :", df_imp[['date', 'client', 'temps', 'fact_client']].head())
            
            if st.button("🚀 Importer définitivement"):
                cols_bdd = ['date', 'collab', 'client', 'description', 'mission_ref', 'temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']
                df_final = df_imp[[c for c in cols_bdd if c in df_imp.columns]]
                df_final.to_sql('prestations', conn, if_exists='append', index=False)
                st.success("Importation terminée ! Allez sur le Dashboard."); st.rerun()

# --- Les autres menus (Encodage, Gestion, Aide) restent identiques ---
elif menu == "📝 Encodage":
    st.info("Utilisez ce formulaire pour les saisies quotidiennes.")
elif menu == "🛠️ Gestion":
    st.info("Modifiez ou supprimez vos données ici.")
elif menu == "ℹ️ Aide & Infos":
    st.write("Système GV2 - Version 1.0")
