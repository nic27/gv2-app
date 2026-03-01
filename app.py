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

@st.dialog("⚠️ RESTAURATION")
def confirm_restore_dialog(uploaded_file):
    st.error("### ATTENTION : ÉCRASEMENT DES DONNÉES")
    if st.button("🔥 CONFIRMER LA RESTAURATION", type="primary", use_container_width=True):
        with open(DB_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Base restaurée avec succès !"); st.rerun()

# --- BARRE LATÉRALE ---
if os.path.exists("logo_gv2.png"):
    st.sidebar.image("logo_gv2.png", use_container_width=True)
st.sidebar.markdown(f"### 🛠️ GV2 Management")
st.sidebar.caption(f"**Version :** {VERSION}")
menu = st.sidebar.radio("Navigation", ["📝 Encodage", "📊 Dashboard", "🛠️ Gestion", "⚙️ Paramètres", "ℹ️ Aide & Infos"])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.header("📊 Dashboard")
    df = pd.read_sql("SELECT * FROM prestations", get_connection())
    if not df.empty:
        df['date_clean'] = df['date'].str.replace('-', '/')
        df['date_dt'] = pd.to_datetime(df['date_clean'], format='%d/%m/%Y', dayfirst=True, errors='coerce')
        df = df.dropna(subset=['date_dt'])
        df['Année'] = df['date_dt'].dt.year
        df['Mois_Label'] = df['date_dt'].dt.strftime('%m/%Y')
        
        st.sidebar.header("🔍 Filtres")
        y_list = sorted(df['Année'].unique(), reverse=True)
        sel_y = st.sidebar.multiselect("Années", y_list, default=y_list)
        mois_options = df[df['Année'].isin(sel_y)].sort_values('date_dt', ascending=False)['Mois_Label'].unique()
        sel_m = st.sidebar.multiselect("Mois", mois_options, default=mois_options)
        
        df_f = df[(df['Année'].isin(sel_y)) & (df['Mois_Label'].isin(sel_m))]
        
        if not df_f.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Heures", f"{df_f['temps'].sum():.2f} h")
            c2.metric("CA HT", f"{df_f['fact_client'].sum():,.2f} €")
            c3.metric("Marge", f"{(df_f['fact_client'].sum() - df_f['fact_interne'].sum()):,.2f} €")
            st.plotly_chart(px.bar(df_f.groupby('client')['fact_client'].sum().reset_index(), x='client', y='fact_client', color='client', color_discrete_map=FORCED_COLORS), use_container_width=True)
        else: st.warning("Sélection vide.")
    else: st.info("Aucune donnée disponible.")

# --- PARAMÈTRES ---
elif menu == "⚙️ Paramètres":
    st.header("⚙️ Configuration")
    conn = get_connection()
    tab_maint, tab_csv = st.tabs(["💾 Maintenance", "📥 Import CSV"])
    
    with tab_maint:
        st.subheader("Sauvegarde et Restauration")
        c1, c2 = st.columns(2)
        with c1:
            st.info("Télécharger la base de données actuelle (.db)")
            if os.path.exists(DB_PATH):
                with open(DB_PATH, "rb") as f:
                    st.download_button(f"📥 Télécharger Backup_{DATE_FILE}", f, f"backup_gv2_{DATE_FILE}.db", use_container_width=True)
        with c2:
            st.warning("Restaurer une base à partir d'un fichier .db")
            up_db = st.file_uploader("Choisir un fichier .db", type="db")
            if up_db and st.button("🚀 Lancer la Restauration"): confirm_restore_dialog(up_db)

    with tab_csv:
        st.subheader("Importation de données CSV")
        up_csv = st.file_uploader("Fichier CSV (Séparateur point-virgule)", type="csv")
        if up_csv:
            df_imp = pd.read_csv(up_csv, sep=';', engine='python')
            
            # Mapping pour correspondre aux colonnes du fichier utilisateur
            mapping = {
                'date': ['Date', 'date'], 'collab': ['collab', 'Collaborateur'],
                'client': ['Nom du client', 'client'], 'description': ['Description'],
                'mission_ref': ['Référence de mission'], 'temps': ['Temps de travail'],
                'tarif_client': ['Tarif horaire client'], 'fact_client': ['Facturation horaire client'],
                'tarif_interne': ['Tarif horaire interne GV2'], 'fact_interne': ['Facturation interne GV2']
            }
            
            new_cols = {c: db_col for db_col, candidates in mapping.items() for c in candidates if c in df_imp.columns}
            df_imp = df_imp.rename(columns=new_cols)

            # Nettoyage
            if 'date' in df_imp.columns: df_imp['date'] = df_imp['date'].astype(str).str.replace('-', '/')
            for col in ['temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']:
                if col in df_imp.columns:
                    df_imp[col] = df_imp[col].astype(str).str.replace('€', '').str.replace(',', '.').str.replace('\xa0', '').str.strip()
                    df_imp[col] = pd.to_numeric(df_imp[col], errors='coerce').fillna(0)

            st.write("Aperçu avant import :", df_imp.head(3))
            
            if st.button("✅ Confirmer l'importation des données"):
                cols_bdd = ['date', 'collab', 'client', 'description', 'mission_ref', 'temps', 'tarif_client', 'fact_client', 'tarif_interne', 'fact_interne']
                df_final = df_imp[[c for c in cols_bdd if c in df_imp.columns]]
                df_final.to_sql('prestations', conn, if_exists='append', index=False)
                
                # MESSAGE DE CONFIRMATION
                st.success(f"🎉 Importation réussie ! {len(df_final)} prestations ont été ajoutées à la base.")
                st.balloons()

# --- AUTRES MENUS ---
elif menu == "📝 Encodage":
    st.subheader("Saisie manuelle")
    st.info("Utilisez cet onglet pour ajouter une prestation unique.")
elif menu == "🛠️ Gestion":
    st.subheader("Modification des données")
    df_g = pd.read_sql("SELECT * FROM prestations ORDER BY id DESC", get_connection())
    st.dataframe(df_g)
elif menu == "ℹ️ Aide & Infos":
    st.write(f"Système de gestion GV2 - Version {VERSION}")
